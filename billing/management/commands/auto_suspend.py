from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from billing.models import Customer, SystemLog, Payment
from network_manager.services import MikrotikAPI

# Above this many past-due accounts, auto-suspend refuses to run and waits
# for a human. A handful of genuine late payers is normal and gets handled
# automatically; hundreds means the data is wrong (bulk import, migration),
# and a cron job must not be the thing that disconnects a third of the
# customer base at 3am.
BULK_SUSPEND_THRESHOLD = 50


class Command(BaseCommand):
    help = "Auto-suspends PPPoE users whose expiration date has passed, or auto-renews them if they have Advance Payment"

    def handle(self, *args, **kwargs):
        now = timezone.now()

        # Fetch all customers where expiration date is in the past and status is active
        due_customers = Customer.objects.filter(
            expires_at__lte=now, status="active", installation_status="installed"
        ).exclude(status__in=["pending", "closed_not_installed"])

        # --- SAFETY VALVE -------------------------------------------------
        # A legacy import can leave hundreds of accounts flagged 'active'
        # with a long-past expiry, because the old PHP system kept paying
        # customers connected by hand and never cleaned up. Suspending all of
        # them in one pass is a mass outage, not a collections action.
        #
        # So above BULK_SUSPEND_THRESHOLD we refuse and demand a human. Staff
        # resolve the backlog through the "Connected, Unpaid" queue in the
        # customers list, which is a deliberate action, not a cron accident.
        # Below the threshold this behaves exactly as before.
        count = due_customers.count()
        if count > BULK_SUSPEND_THRESHOLD:
            self.stdout.write(
                self.style.ERROR(
                    f"ABORTED: {count} active accounts are past due, above the "
                    f"auto-suspend limit of {BULK_SUSPEND_THRESHOLD}.\n"
                    f"  Nothing was suspended and nothing was changed.\n"
                    f"  This is almost always a bulk import or a lapsed migration, "
                    f"not {count} individual late payers.\n"
                    f"  Review them in Customers -> 'Connected, Unpaid' and "
                    f"reconnect or suspend them deliberately."
                )
            )
            SystemLog.objects.create(
                table_name="Customer",
                record_id="0",
                action="AUTO_SUSPEND_ABORTED",
                changed_by="System (Auto-Suspend)",
                target_name="auto_suspend",
                old_data="",
                new_data=(
                    f"Aborted: {count} accounts past due exceeds the limit of "
                    f"{BULK_SUSPEND_THRESHOLD}. No customers were suspended."
                ),
            )
            return

        # --- CONNECTIVITY GATE -------------------------------------------
        # Never suspend a customer we cannot actually see. If the routers are
        # unreachable we have no idea who is really online, and cutting people
        # off blind is exactly the failure this guards against.
        from billing.customer_state import network_visibility

        network_visible, _ = network_visibility()
        if not network_visible:
            self.stdout.write(
                self.style.WARNING(
                    "ABORTED: the routers are not reachable, so we cannot tell "
                    "who is genuinely online. Suspending blind would cut off "
                    "paying customers. No customers were suspended."
                )
            )
            return

        suspended_count = 0
        renewed_count = 0
        rogue_suspended_count = 0

        if not due_customers.exists():
            self.stdout.write(
                self.style.WARNING("No active customers are currently past due.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {due_customers.count()} active past due customers. Starting check..."
                )
            )

        for customer in due_customers:
            plan_price = customer.plan.price if customer.plan else 0

            # 1. Check if they have enough Advance Payment (outstanding_balance) to auto-renew
            # In our system, negative outstanding_balance means credit (Advance Payment)
            if plan_price > 0 and customer.outstanding_balance <= -plan_price:
                # --- AUTO RENEW ---
                from billing.views import calculate_new_expiration_date

                new_expiry = calculate_new_expiration_date(
                    customer.expires_at, float(plan_price), float(plan_price)
                )

                customer.expires_at = new_expiry
                customer.outstanding_balance += plan_price
                customer.save()

                # Log the auto-renewal payment record
                Payment.objects.create(
                    customer=customer,
                    username=customer.pppoe_username,
                    plan_name=customer.plan.name if customer.plan else None,
                    amount=plan_price,
                    payment_method="advance_payment",
                    reference_no="AUTO-RENEW",
                    reason="Auto-renewed from Advance Payment wallet",
                    expires_at=new_expiry,
                    adjusted_by="System",
                )

                SystemLog.objects.create(
                    table_name="Customer",
                    record_id=str(customer.id),
                    action="UPDATE",
                    changed_by="System (Auto-Renew)",
                    target_name=customer.full_name,
                    old_data=f"expires_at: {customer.expires_at}",
                    new_data=f"Auto-renewed using Advance Payment. New expires_at: {new_expiry}",
                )

                renewed_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[AUTO-RENEW] {customer.pppoe_username} auto-renewed for 1 month using Advance Payment."
                    )
                )
                continue

            # 2. Otherwise, suspend normally
            # Skip if they don't have a linked Mikrotik device
            if not customer.mikrotik_device:
                self.stdout.write(
                    self.style.ERROR(
                        f"[WARNING] {customer.pppoe_username} has no Mikrotik device assigned. Skipping."
                    )
                )
                continue

            try:
                # Initialize the new MikrotikAPI utility
                mt = MikrotikAPI(customer.mikrotik_device)

                if getattr(mt, "is_read_only", False):
                    # ROUTER_MODE=read_only: Router write is blocked. Do not mark customer as suspended.
                    customer.sync_status = "Blocked"
                    customer.save(update_fields=["sync_status"])
                    self.stdout.write(
                        self.style.WARNING(
                            f"[BLOCKED] Router write blocked by ROUTER_MODE=read_only for {customer.pppoe_username}. Status remains {customer.status}."
                        )
                    )
                    continue

                # Suspend the user (handles MAC-level drop, secret disable, and active session kick)
                success, message = mt.suspend_pppoe_user(customer.pppoe_username)

                if success:
                    # Update customer status in the DB
                    customer.status = "suspended"
                    customer.save()

                    # Create an audit log entry
                    SystemLog.objects.create(
                        table_name="Customer",
                        record_id=str(customer.id),
                        action="UPDATE",
                        changed_by="System (Auto-Suspend)",
                        target_name=customer.full_name,
                        old_data="status: active",
                        new_data="status: suspended",
                    )

                    suspended_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[SUCCESS] Suspended {customer.pppoe_username} on {customer.mikrotik_device.device_name}: {message}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[FAILED] Failed to suspend {customer.pppoe_username} on Mikrotik: {message}"
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[ERROR] Unexpected error suspending {customer.pppoe_username}: {str(e)}"
                    )
                )

        # -------------------------------------------------------------
        # PART 2: Auto-Suspend Suspicious/Rogue Accounts
        # -------------------------------------------------------------
        rogue_customers = [
            c
            for c in Customer.objects.filter(
                status="active", is_verified=False, installation_status="installed"
            ).exclude(status__in=["pending", "closed_not_installed"])
            if c.is_suspicious
        ]

        if not rogue_customers:
            self.stdout.write(
                self.style.WARNING("No active rogue/suspicious customers found.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {len(rogue_customers)} unverified rogue customers. Starting check..."
                )
            )

            for customer in rogue_customers:
                if not customer.mikrotik_device:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[WARNING] Rogue customer {customer.pppoe_username} has no Mikrotik device assigned. Skipping."
                        )
                    )
                    continue

                try:
                    mt = MikrotikAPI(customer.mikrotik_device)

                    if getattr(mt, "is_read_only", False):
                        # ROUTER_MODE=read_only: Router write is blocked. Do not mark customer as suspended.
                        customer.sync_status = "Blocked"
                        customer.save(update_fields=["sync_status"])
                        self.stdout.write(
                            self.style.WARNING(
                                f"[BLOCKED] Router write blocked by ROUTER_MODE=read_only for rogue {customer.pppoe_username}."
                            )
                        )
                        continue

                    # Suspend the user (kicks session, drops secret)
                    success, message = mt.suspend_pppoe_user(customer.pppoe_username)

                    if success:
                        customer.status = "suspended"
                        customer.save()

                        SystemLog.objects.create(
                            table_name="Customer",
                            record_id=str(customer.id),
                            action="UPDATE",
                            changed_by="System (Auto-Suspend Rogue)",
                            target_name=customer.full_name,
                            old_data="status: active",
                            new_data="status: suspended (Rogue Account)",
                        )

                        rogue_suspended_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[SUCCESS] Suspended Rogue {customer.pppoe_username} on {customer.mikrotik_device.device_name}: {message}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f"[FAILED] Failed to suspend Rogue {customer.pppoe_username} on Mikrotik: {message}"
                            )
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[ERROR] Unexpected error suspending Rogue {customer.pppoe_username}: {str(e)}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"[DONE] Process complete. Suspended Due: {suspended_count} | Auto-Renewed: {renewed_count} | Suspended Rogues: {rogue_suspended_count}"
            )
        )
