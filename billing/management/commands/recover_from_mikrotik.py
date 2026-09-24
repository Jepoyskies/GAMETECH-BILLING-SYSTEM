import logging
from django.core.management.base import BaseCommand
from billing.models import Customer, SubscriptionPlan
from network_manager.models import MikrotikDevice
from network_manager.sync_services import MikrotikAPI

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Recovers local database by fetching all PPPoE secrets directly from the Mikrotik router."

    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.WARNING("Starting emergency database recovery from Mikrotik...")
        )

        # Get active Mikrotik Device (assuming single router for now)
        device = MikrotikDevice.objects.first()
        if not device:
            self.stdout.write(
                self.style.ERROR(
                    "No active Mikrotik device found. Please recreate it in the Admin panel first."
                )
            )
            return

        self.stdout.write(
            f"Connecting to Mikrotik router: {device.device_name} ({device.ip_address})..."
        )

        try:
            api = MikrotikAPI(
                ip_address=device.ip_address,
                username=device.api_username,
                password=device.api_password,
                port=device.api_port,
            )

            result = api.get_all_pppoe_users()
            if not result.get("success"):
                self.stdout.write(
                    self.style.ERROR(f"Failed to fetch secrets: {result.get('error')}")
                )
                return

            secrets = result.get("data", [])
            self.stdout.write(f"Found {len(secrets)} PPP secrets on the router.")

            created_count = 0
            updated_count = 0
            skipped_count = 0
            for s in secrets:
                username = s.get("name")
                password = s.get("password", "")
                profile = s.get("profile", "default")
                caller_id = s.get("caller-id", "")

                # We skip empty usernames or default Mikrotik templates
                if not username or username == "default":
                    skipped_count += 1
                    continue

                # Match Profile to SubscriptionPlan
                plan = SubscriptionPlan.objects.filter(name__iexact=profile).first()

                # Check if customer already exists by PPPoE username
                customer, created = Customer.objects.get_or_create(
                    pppoe_username=username,
                    defaults={
                        "full_name": username,  # We default to username since Mikrotik doesn't store full name
                        "pppoe_password": password,
                        "plan": plan,
                        "mikrotik_device": device,
                        "mac_address": caller_id,
                        "status": "active",
                        "installation_status": "installed",
                        "source": "router_sync",
                        "created_form_by": "MikroTik Recovery",
                    },
                )

                if created:
                    created_count += 1
                else:
                    # Update existing just in case
                    if customer.pppoe_password != password or customer.plan != plan:
                        customer.pppoe_password = password
                        customer.plan = plan
                        customer.save(update_fields=["pppoe_password", "plan"])
                        updated_count += 1
                    else:
                        skipped_count += 1

            from billing.models import SystemLog
            SystemLog.objects.create(
                table_name="Customer",
                record_id="0",
                action="ROUTER_RECOVERY_IMPORT",
                changed_by="recover_from_mikrotik",
                target_name=device.device_name,
                old_data="",
                new_data=f"Emergency router recovery from {device.device_name}: {created_count} created, {updated_count} updated, {skipped_count} skipped.",
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nEmergency Recovery Complete! Restored: {created_count} created, {updated_count} updated, {skipped_count} skipped from Mikrotik."
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Unexpected error during recovery: {str(e)}")
            )
