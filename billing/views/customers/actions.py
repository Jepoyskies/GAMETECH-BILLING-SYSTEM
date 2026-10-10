from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
    permission_required,
)
from django.views.decorators.http import require_POST
from billing.decorators import role_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, Max
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime
from billing.models import (
    SystemAdmin,
    SubscriptionPlan,
    Agent,
    AccountType,
    Customer,
    Barangay,
    Payment,
    Rebate,
    SystemLog,
    SmsLog,
    CignalPlay,
    AuditLog,
    AddOnRequest,
    Notification,
    ImprovementRequest,
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar
from billing.views.services import get_categorized_plans


@login_required
@permission_required("billing.change_customer", raise_exception=True)
def customer_force_suspend(request, username):
    """Force-suspend a customer.

    Billing and hardware are INDEPENDENT domains (AGENTS.md Rule 35). The CRM
    status is the billing truth and must be written regardless of what the
    router does. Previously the whole DB update sat inside `if success:` from
    the router call, which meant:
      * with ROUTER_MODE=read_only (or any router timeout) collections staff
        could not suspend anybody -- the arrears workflow was dead, and
      * a customer with no device assigned could never be suspended at all.

    Now: CRM first, router second, and the two outcomes are reported separately
    so staff always know whether the line is actually cut off.
    """
    if request.method != "POST":
        return redirect("customer_list")

    customer = get_object_or_404(Customer, pppoe_username=username)

    reason = (request.POST.get("reason") or "").strip() or "manual suspension"

    # --- 1. BILLING (always) ---
    customer.status = "suspended"
    customer.expires_at = None
    customer.save(update_fields=["status", "expires_at"])

    from billing.models import AuditLog
    AuditLog.objects.create(
        admin_user=request.user if request.user.is_authenticated else None,
        customer=customer,
        action_type="FORCE_SUSPEND",
        remarks=reason,
    )

    # --- 2. HARDWARE (best effort, reported separately) ---
    if not customer.mikrotik_device:
        messages.warning(
            request,
            f"{username} is now SUSPENDED in billing, but has no MikroTik device "
            f"assigned so nothing was changed on the router.",
        )
        return redirect("view_customer", customer_id=customer.id)

    try:
        from network_manager.services import MikrotikAPI

        api = MikrotikAPI(customer.mikrotik_device)
        ok, msg = api.suspend_pppoe_user(username)
    except Exception as exc:
        ok, msg = False, f"{type(exc).__name__}: {exc}"

    if ok:
        messages.success(
            request,
            f"{username} suspended in billing and on {customer.mikrotik_device.device_name}.",
        )
    else:
        messages.warning(
            request,
            f"{username} is now SUSPENDED in billing, but the router did not "
            f"confirm the cut-off ({msg}). The line may still be live on the "
            f"router - check the Sync Manager.",
        )
    return redirect("view_customer", customer_id=customer.id)


@role_required(["Admin", "Editor"])
@login_required
def customer_kick_session(request, username):
    """Manually kicks the active PPPoE session without altering their billing status"""
    if request.method == "POST":
        customer = get_object_or_404(Customer, pppoe_username=username)
        kicked = False
        kicked_device_name = ""
        from network_manager.models import MikrotikDevice
        from network_manager.services import MikrotikAPI

        if customer.mikrotik_device:
            api = MikrotikAPI(customer.mikrotik_device)
            success, msg = api.kick_active_user(username)
            if success:
                kicked = True
                kicked_device_name = customer.mikrotik_device.device_name

        if not kicked:
            # Check other routers (e.g. if user was transferred or active on old router)
            exclude_id = customer.mikrotik_device_id if customer.mikrotik_device_id else -1
            for other_dev in MikrotikDevice.objects.exclude(id=exclude_id):
                try:
                    oapi = MikrotikAPI(other_dev)
                    osuccess, omsg = oapi.kick_active_user(username)
                    if osuccess:
                        kicked = True
                        kicked_device_name = other_dev.device_name
                        break
                except Exception:
                    pass

        if kicked:
            target_info = f" from {kicked_device_name}" if kicked_device_name else ""
            if customer.mikrotik_device and kicked_device_name != customer.mikrotik_device.device_name:
                messages.success(
                    request,
                    f"Active session for {username} was kicked{target_info}. Modem will now renegotiate onto {customer.mikrotik_device.device_name}."
                )
            else:
                messages.success(
                    request, f"Active session for {username} was kicked successfully."
                )
        else:
            messages.error(request, f"No active session found for {username} across any online router.")

        return redirect("view_customer", customer_id=customer.id)
    return redirect("customer_list")


@login_required
@permission_required("billing.change_customer", raise_exception=True)
def customer_force_reactivate(request, username):
    """Manually force reactivates a customer using Master Password and logs it to AuditLog"""
    if request.method == "POST":
        import os

        admin_password = request.POST.get("admin_password", "")
        reason = request.POST.get("override_reason", "")
        customer = get_object_or_404(Customer, pppoe_username=username)

        # Verify that the user is a superuser and entered their correct password
        if not request.user.is_superuser or not request.user.check_password(
            admin_password
        ):
            messages.error(
                request,
                "Admin Override Failed: Invalid Password or you are not a Superuser.",
            )
            return redirect("view_customer", customer_id=customer.id)

        if not reason.strip():
            messages.error(
                request, "Admin Override Failed: Reason for override is required."
            )
            return redirect("view_customer", customer_id=customer.id)

        # --- 1. BILLING (always) ---
        # Same Rule 35 split as force_suspend: the CRM status is the billing
        # truth and does not depend on the router answering. Previously three
        # nested `if <router call succeeded>` gates sat in front of the DB
        # update, so under ROUTER_MODE=read_only -- or on any router timeout --
        # an admin override silently did nothing at all.
        customer.status = "active"
        # DO NOT update expiration date or outstanding balance: reactivating
        # restores service, it is not a payment.
        customer.save(update_fields=["status"])

        from billing.models import AuditLog

        AuditLog.objects.create(
            admin_user=(request.user if request.user.is_authenticated else None),
            customer=customer,
            action_type="FORCE_REACTIVATE",
            remarks=reason,
        )

        # --- 2. HARDWARE (best effort, reported separately) ---
        if not customer.mikrotik_device:
            messages.warning(
                request,
                f"{username} is now ACTIVE in billing, but has no MikroTik device "
                f"assigned so nothing was changed on the router.",
            )
            return redirect("view_customer", customer_id=customer.id)

        target_profile = customer.plan.name if customer.plan else "default"
        steps, problems = [], []
        try:
            from network_manager.services import MikrotikAPI

            api = MikrotikAPI(customer.mikrotik_device)

            ok, msg = api.enable_pppoe_user(username)
            steps.append(("enable secret", ok, msg))
            if ok:
                ok2, msg2 = api.set_user_pppoe_profile(username, target_profile)
                steps.append((f"profile -> {target_profile}", ok2, msg2))
                if ok2:
                    ok3, msg3 = api.kick_active_user(username)
                    steps.append(("kick session", ok3, msg3))
        except Exception as exc:
            problems.append(f"{type(exc).__name__}: {exc}")

        failed = [s for s in steps if not s[1]]
        if not steps or failed or problems:
            detail = "; ".join([f"{label}: {msg}" for label, ok, msg in steps if not ok]
                               + problems) or "router not contacted"
            messages.warning(
                request,
                f"{username} is now ACTIVE in billing, but the router did not fully "
                f"confirm service ({detail}). Check the Sync Manager.",
            )
        else:
            messages.success(
                request,
                f"Customer {username} force-reactivated via Master Override.",
            )
        return redirect("view_customer", customer_id=customer.id)
    return redirect("customer_list")


@login_required
@role_required(["Admin"])
def edit_customer_expiration(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == "POST":
        new_date_str = request.POST.get("expires_at")
        old_date = (
            customer.expires_at.strftime("%Y-%m-%d %H:%M:%S")
            if customer.expires_at
            else "None"
        )
        if new_date_str and new_date_str.strip():
            from django.utils.dateparse import parse_datetime
            from django.utils import timezone
            from billing.models import SystemLog

            new_date = parse_datetime(new_date_str)
            if new_date:
                if timezone.is_naive(new_date):
                    new_date = timezone.make_aware(
                        new_date, timezone.get_current_timezone()
                    )
                customer._preserve_expiration = True
                customer.expires_at = new_date
                customer.save()
                SystemLog.objects.create(
                    table_name="Customer",
                    record_id=str(customer.id),
                    action="UPDATE",
                    changed_by=request.user.username,
                    old_data=f"Expiration: {old_date}",
                    new_data=f"Expiration: {new_date.strftime('%Y-%m-%d %H:%M:%S')}",
                )
                messages.success(
                    request,
                    f"Expiration date for {customer.full_name} has been successfully updated.",
                )
            else:
                messages.error(request, "Invalid date format.")
        else:
            from billing.models import SystemLog

            customer.expires_at = None
            customer.save()
            SystemLog.objects.create(
                table_name="Customer",
                record_id=str(customer.id),
                action="UPDATE",
                changed_by=request.user.username,
                old_data=f"Expiration: {old_date}",
                new_data="Expiration: None",
            )
            messages.success(
                request,
                f"Expiration date for {customer.full_name} has been cleared (set to None).",
            )
    return redirect("view_customer", customer_id=customer.id)


@login_required
@role_required(["Admin"])
def edit_customer_balance(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == "POST":
        admin_password = request.POST.get("admin_password")
        new_balance_str = request.POST.get("outstanding_balance")
        new_expiration_str = request.POST.get("new_expiration_date")

        if not request.user.check_password(admin_password):
            messages.error(
                request,
                "Incorrect admin password. Balance reset cancelled for security reasons.",
            )
            return redirect("view_customer", customer_id=customer.id)

        if new_balance_str is not None:
            try:
                from decimal import Decimal
                from billing.models import SystemLog, Notification
                from django.utils.dateparse import parse_datetime
                from django.utils import timezone
                from billing.utils import get_customer_base_expiration

                new_balance = Decimal(new_balance_str)
                old_balance = customer.outstanding_balance
                old_expiration = customer.expires_at
                reverted_expiry = get_customer_base_expiration(customer)

                # Parse and update expiration date with timezone awareness
                new_expiration = None
                if new_expiration_str:
                    new_expiration = parse_datetime(new_expiration_str)
                    if new_expiration and timezone.is_naive(new_expiration):
                        new_expiration = timezone.make_aware(
                            new_expiration, timezone.get_current_timezone()
                        )

                # If resetting balance to 0, automatically revert to Month 1 if not manually set to another custom date
                if (new_balance == Decimal("0.00") or new_balance == 0):
                    if not new_expiration or new_expiration == old_expiration:
                        new_expiration = reverted_expiry

                if new_expiration:
                    customer.expires_at = new_expiration

                customer.outstanding_balance = new_balance
                customer.save()

                # Check if it was a reset/decrease
                is_reset = new_balance < old_balance or new_balance == Decimal("0.00")
                action_name = "BALANCE_RESET" if is_reset else "UPDATE"
                old_exp_str = old_expiration.strftime("%Y-%m-%d %H:%M") if old_expiration else "None"
                new_exp_str = customer.expires_at.strftime("%Y-%m-%d %H:%M") if customer.expires_at else "None"

                SystemLog.objects.create(
                    table_name="Customer",
                    record_id=str(customer.id),
                    action=action_name,
                    changed_by=request.user.username,
                    target_name=customer.full_name,
                    old_data=f"Balance: ₱{old_balance} | Expires: {old_exp_str}",
                    new_data=f"Balance: ₱{new_balance} | Expires: {new_exp_str}",
                )

                if is_reset:
                    Notification.objects.create(
                        message=f"CRITICAL: {request.user.username} performed a balance override for {customer.full_name}. Balance changed from ₱{old_balance} to ₱{new_balance}.",
                        type="alert",
                        link=f"/customers/view/{customer.id}/",
                    )

                messages.success(
                    request,
                    f"Advance payment for {customer.full_name} updated. Expiration set to {customer.expires_at.strftime('%b %d, %Y %I:%M %p')}.",
                )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error resetting balance: {e}")
                messages.error(
                    request, "Invalid balance amount or expiration date format."
                )
    return redirect("view_customer", customer_id=customer.id)


@login_required
def statement_of_account_view(request, customer_id):
    customer = get_object_or_404(
        Customer.objects.select_related("plan", "barangay", "mikrotik_device"),
        id=customer_id,
    )
    payments = customer.payments.all().order_by("-paid_at")

    date_from = request.GET.get("from")
    date_to = request.GET.get("to")

    if date_from and date_to:
        payments = payments.filter(
            paid_at__date__gte=date_from, paid_at__date__lte=date_to
        )

    total_paid = sum(p.amount for p in payments)

    context = {
        "customer": customer,
        "payments": payments,
        "date_from": date_from,
        "date_to": date_to,
        "total_paid": total_paid,
        "current_date": timezone.now(),
    }
    return render(request, "billing/statement_of_account.html", context)


@require_POST
@role_required(["Admin", "Editor"])
@login_required
def bulk_transfer_router(request):
    """
    Handles bulk moving customers to a different Mikrotik router.
    """
    if request.method == "POST":
        customer_ids = request.POST.getlist("customer_ids")
        target_device_id = request.POST.get("target_device_id")
        kick_now = request.POST.get("kick_now") in ["1", "true", "True", "on"]

        if not customer_ids or not target_device_id:
            messages.error(request, "Please select customers and a target router.")
            return redirect("customer_list")

        try:
            from network_manager.models import MikrotikDevice

            target_device = MikrotikDevice.objects.get(id=target_device_id)

            transferred_count = 0
            for cid in customer_ids:
                customer = Customer.objects.get(id=cid)
                if str(customer.mikrotik_device_id) != str(target_device_id):
                    # Keep track of old device ID so the signal knows to delete the secret
                    customer._original_mikrotik_device_id = customer.mikrotik_device_id
                    customer._kick_active_on_transfer = kick_now

                    customer.mikrotik_device = target_device
                    customer.save()  # Triggers post_save signal
                    transferred_count += 1

            action_desc = " (active sessions kicked for immediate reconnection)" if kick_now else " (sessions preserved on old router until hardware swap)"
            messages.success(
                request,
                f"Successfully transferred {transferred_count} customers to {target_device.device_name}{action_desc}.",
            )
        except Exception as e:
            messages.error(request, f"Error during transfer: {str(e)}")

        referrer = request.META.get("HTTP_REFERER")
        if referrer:
            return redirect(referrer)
        return redirect("customer_list")


@require_POST
@role_required(["Admin", "Editor"])
@login_required
def verify_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if not customer.is_verified:
        customer.is_verified = True
        customer.save(update_fields=["is_verified"])

        SystemLog.objects.create(
            table_name="Customer",
            record_id=str(customer.id),
            action="UPDATE",
            changed_by=request.user.username,
            target_name=customer.full_name,
            old_data="is_verified: False",
            new_data="is_verified: True (Admin Verified Rogue Account)",
        )

        messages.success(
            request,
            f"Account {customer.pppoe_username} has been verified and protected from auto-suspension.",
        )
    else:
        messages.info(request, "Account is already verified.")

    return redirect("view_customer", customer_id=customer.id)


@require_POST
@role_required(["Admin", "Editor"])
@login_required
def unverify_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if customer.is_verified:
        customer.is_verified = False
        customer.save(update_fields=["is_verified"])

        SystemLog.objects.create(
            table_name="Customer",
            record_id=str(customer.id),
            action="UPDATE",
            changed_by=request.user.username,
            target_name=customer.full_name,
            old_data="is_verified: True",
            new_data="is_verified: False (Admin Unverified Account)",
        )

        messages.success(
            request,
            f"Account {customer.pppoe_username} has been unverified and is now subject to regular checks.",
        )
    else:
        messages.info(request, "Account is not verified.")

    return redirect("view_customer", customer_id=customer.id)


@require_POST
@role_required(["Admin", "Editor"])
@login_required
def mark_customer_installed(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    installed_at_str = request.POST.get("installed_at")
    plan_id = request.POST.get("plan_id")
    amount_str = request.POST.get("amount")
    payment_method = request.POST.get("payment_method") or "Cash"
    reference_no = (request.POST.get("reference_no") or "").strip()
    expires_at_str = request.POST.get("expires_at")

    if installed_at_str:
        try:
            installed_at = timezone.datetime.strptime(installed_at_str, "%Y-%m-%d")
            if timezone.is_naive(installed_at):
                installed_at = timezone.make_aware(installed_at)
        except ValueError:
            installed_at = timezone.now()
    else:
        installed_at = timezone.now()

    customer.installation_status = "installed"
    customer.installed_at = installed_at
    if customer.status == "pending":
        customer.status = "active"

    # Update plan if selected
    old_plan_name = customer.plan.name if customer.plan else "None"
    if plan_id:
        new_plan = SubscriptionPlan.objects.filter(id=plan_id).first()
        if new_plan:
            customer.plan = new_plan

    # Parse or auto-calculate expiration / first due date
    if expires_at_str:
        try:
            exp_dt = timezone.datetime.strptime(expires_at_str, "%Y-%m-%d")
            exp_dt = exp_dt.replace(hour=23, minute=59, second=59)
            if timezone.is_naive(exp_dt):
                exp_dt = timezone.make_aware(exp_dt)
            customer.expires_at = exp_dt
        except ValueError:
            pass
    elif not customer.expires_at:
        monthly_price = float(customer.plan.price) if customer.plan else 0.0
        try:
            pay_amt = float(amount_str) if amount_str else 0.0
        except (ValueError, TypeError):
            pay_amt = 0.0

        if monthly_price > 0 and pay_amt > 0:
            from billing.views import calculate_new_expiration_date

            customer.expires_at = calculate_new_expiration_date(
                installed_at, pay_amt, monthly_price
            )
        else:
            customer.expires_at = installed_at + timedelta(days=30)

    customer.save()

    # Process Initial Payment if provided and > 0
    amount = 0.0
    if amount_str:
        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            amount = 0.0

    if amount > 0:
        Payment.objects.create(
            customer=customer,
            username=customer.pppoe_username,
            plan_name=customer.plan.name if customer.plan else None,
            mikrotik_device_name=(
                customer.mikrotik_device.device_name
                if customer.mikrotik_device
                else None
            ),
            amount=amount,
            payment_method=payment_method,
            reference_no=reference_no,
            reason="Initial payment upon installation",
            expires_at=customer.expires_at,
            payment_date_received=installed_at,
            paid_at=timezone.now(),
            adjusted_by=request.user.username,
        )

        Notification.objects.create(
            title=f"Payment Received: ₱{amount:,.2f}",
            message=f"{customer.full_name} paid ₱{amount:,.2f} via {payment_method} upon installation.",
            notification_type="payment",
            link="/logs/payments/",
        )

    # Build comprehensive audit log
    new_data_lines = [
        "Installation Status: Installed",
        f"Installed At: {customer.installed_at.strftime('%Y-%m-%d') if customer.installed_at else 'N/A'}",
        f"Plan: {customer.plan.name if customer.plan else 'None'}",
        f"First Due / Expires At: {customer.expires_at.strftime('%Y-%m-%d %H:%M') if customer.expires_at else 'N/A'}",
        f"Status: {customer.status}",
    ]
    if amount > 0:
        ref_text = f" (Ref: {reference_no})" if reference_no else ""
        new_data_lines.append(
            f"Initial Payment: ₱{amount:,.2f} via {payment_method}{ref_text}"
        )

    SystemLog.objects.create(
        table_name="Customer",
        record_id=str(customer.id),
        action="INSTALLATION",
        changed_by=request.user.username,
        target_name=customer.full_name,
        old_data=f"Installation Status: Pending | Plan: {old_plan_name}",
        new_data="\n".join(new_data_lines),
    )

    # 2-Way Sync: Close any open dispatch JobTicket for this customer
    try:
        from dispatch.models import JobTicket
        JobTicket.objects.filter(
            customer=customer,
            ticket_type="INSTALLATION",
            status__in=["PENDING", "ASSIGNED", "IN_PROGRESS"],
        ).update(
            status="COMPLETED",
            done_at=timezone.now(),
            time_accomplish=timezone.now(),
        )
    except Exception:
        pass

    success_msg = f"Customer {customer.full_name} has been marked as Installed! Account is now active."
    if amount > 0:
        success_msg += f" Initial payment of ₱{amount:,.2f} recorded."
    messages.success(request, success_msg)
    return redirect("view_customer", customer_id=customer.id)

@require_POST
@role_required(["Admin", "Editor", "CSR"])
@login_required
def file_repair_request(request, customer_id):
    """File a REPAIR ticket for an existing subscriber, from their record.

    THE GAP THIS CLOSES
    -------------------
    The customer detail page could suspend, kick, edit a balance, edit an
    expiry and mark someone installed, but had no way to send them to
    dispatch. Staff had to leave the subscriber, go to Dispatch and re-enter
    the same details by hand -- so repairs were raised inconsistently or not
    at all, which is exactly the step the business runs on.

    REPAIR tickets are already fully wired downstream (analytics, reports, QA,
    technician mobile), so this only had to create the ticket.

    Deliberately does NOT touch a router. Creating a ticket is our own
    business record; dispatch assignment and any later action are separate,
    human steps behind their own gates.
    """
    customer = get_object_or_404(Customer, id=customer_id)

    issue = (request.POST.get("issue") or "").strip()
    priority = request.POST.get("priority") or "medium"
    if priority not in ("low", "medium", "high", "urgent"):
        priority = "medium"

    if not issue:
        messages.error(
            request,
            "Describe the problem first -- a repair ticket with no issue text "
            "is not something a technician can act on.",
        )
        return redirect("view_customer", customer_id=customer.id)

    from dispatch.models import JobTicket
    from dispatch.utils import generate_ticket_number

    with transaction.atomic():
        ticket = JobTicket.objects.create(
            ticket_number=generate_ticket_number(),
            ticket_type="REPAIR",
            status="PENDING",
            priority=priority,
            customer=customer,
            mikrotik_device=customer.mikrotik_device,
            client_name=customer.full_name,
            contact_number=customer.phone,
            address=getattr(customer, "address", "") or "",
            barangay=customer.barangay,
            source_tab="CLIENT_CONCERNS",
            is_test_data=getattr(customer, "is_test_data", False),
        )

    messages.success(
        request,
        "Repair request {} filed and sent to dispatch. Assign a technician "
        " from the Dispatch queue.".format(ticket.ticket_number),
    )
    return redirect("view_customer", customer_id=customer.id)
