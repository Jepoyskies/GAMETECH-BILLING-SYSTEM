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
    """Manually force suspends a customer (updates profile, kicks session, and updates DB status)"""
    if request.method == "POST":
        customer = get_object_or_404(Customer, pppoe_username=username)
        if customer.mikrotik_device:
            from network_manager.services import MikrotikAPI

            api = MikrotikAPI(customer.mikrotik_device)
            success, msg = api.suspend_pppoe_user(username)
            if success:
                customer.status = "suspended"
                customer.save()
                messages.success(
                    request, f"Customer {username} has been forcefully suspended."
                )
            else:
                messages.error(request, f"Failed to suspend {username}: {msg}")
        else:
            messages.error(request, "Customer has no Mikrotik device assigned.")
        return redirect("view_customer", customer_id=customer.id)
    return redirect("customer_list")


@login_required
def customer_kick_session(request, username):
    """Manually kicks the active PPPoE session without altering their billing status"""
    if request.method == "POST":
        customer = get_object_or_404(Customer, pppoe_username=username)
        if customer.mikrotik_device:
            from network_manager.services import MikrotikAPI

            api = MikrotikAPI(customer.mikrotik_device)
            success, msg = api.kick_active_user(username)
            if success:
                messages.success(
                    request, f"Active session for {username} was kicked successfully."
                )
            else:
                messages.error(request, f"Failed to kick session for {username}: {msg}")
        else:
            messages.error(request, "Customer has no Mikrotik device assigned.")
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

        if customer.mikrotik_device:
            from network_manager.services import MikrotikAPI

            api = MikrotikAPI(customer.mikrotik_device)

            # Use their plan name as the profile, or "default" if no plan is assigned
            target_profile = customer.plan.name if customer.plan else "default"

            # 1. Enable User (removes bridge drop rule and enables ppp secret)
            enable_success, enable_msg = api.enable_pppoe_user(username)
            if enable_success:
                # 2. Update Profile
                prof_success, prof_msg = api.set_user_pppoe_profile(
                    username, target_profile
                )
                if prof_success:
                    # 3. Kick Session (allows modem to redial and gain internet)
                    kick_success, kick_msg = api.kick_active_user(username)

                    # 4. Update DB
                    customer.status = "active"
                    # DO NOT update expiration date or outstanding balance
                    customer.save()

                    # 5. Log the override in the new AuditLog model
                    from billing.models import AuditLog

                    AuditLog.objects.create(
                        admin_user=(
                            request.user if request.user.is_authenticated else None
                        ),
                        customer=customer,
                        action_type="FORCE_REACTIVATE",
                        remarks=reason,
                    )

                    messages.success(
                        request,
                        f"Customer {username} force-reactivated via Master Override.",
                    )
                else:
                    messages.error(
                        request, f"Failed to restore profile for {username}: {prof_msg}"
                    )
            else:
                messages.error(
                    request, f"Failed to enable user {username}: {enable_msg}"
                )
        else:
            messages.error(request, "Customer has no Mikrotik device assigned.")
        return redirect("view_customer", customer_id=customer.id)
    return redirect("customer_list")


@login_required
@role_required(["Admin"])
def edit_customer_expiration(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == "POST":
        new_date_str = request.POST.get("expires_at")
        if new_date_str:
            from django.utils.dateparse import parse_datetime
            from billing.models import SystemLog

            new_date = parse_datetime(new_date_str)
            if new_date:
                old_date = (
                    customer.expires_at.strftime("%Y-%m-%d %H:%M:%S")
                    if customer.expires_at
                    else "None"
                )
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

                new_balance = Decimal(new_balance_str)
                old_balance = customer.outstanding_balance
                old_expiration = customer.expires_at

                # Parse and update expiration date
                if new_expiration_str:
                    new_expiration = parse_datetime(new_expiration_str)
                    if new_expiration:
                        customer.expires_at = new_expiration

                customer.outstanding_balance = new_balance
                customer.save()

                # Check if it was a reset/decrease
                is_reset = new_balance < old_balance or new_balance == Decimal("0.00")
                action_name = "BALANCE_RESET" if is_reset else "UPDATE"

                SystemLog.objects.create(
                    table_name="Customer",
                    record_id=str(customer.id),
                    action=action_name,
                    changed_by=request.user.username,
                    target_name=customer.full_name,
                    old_data=f"Balance: ₱{old_balance} | Expires: {old_expiration.strftime('%Y-%m-%d') if old_expiration else 'None'}",
                    new_data=f"Balance: ₱{new_balance} | Expires: {customer.expires_at.strftime('%Y-%m-%d') if customer.expires_at else 'None'}",
                )

                # Send global alert to all admins if balance was reset
                if is_reset:
                    Notification.objects.create(
                        message=f"CRITICAL: {request.user.username} performed a balance override for {customer.full_name}. Balance changed from ₱{old_balance} to ₱{new_balance}.",
                        type="alert",
                        link=f"/customers/view/{customer.id}/",
                    )

                messages.success(
                    request,
                    f"Advance payment for {customer.full_name} has been securely updated.",
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
    customer = get_object_or_404(Customer, id=customer_id)
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


@role_required(["Admin", "Editor"])
@login_required
def bulk_transfer_router(request):
    """
    Handles bulk moving customers to a different Mikrotik router.
    """
    if request.method == "POST":
        customer_ids = request.POST.getlist("customer_ids")
        target_device_id = request.POST.get("target_device_id")

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

                    customer.mikrotik_device = target_device
                    customer.save()  # Triggers post_save signal
                    transferred_count += 1

            messages.success(
                request,
                f"Successfully transferred {transferred_count} customers to {target_device.device_name}.",
            )
        except Exception as e:
            messages.error(request, f"Error during transfer: {str(e)}")

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
