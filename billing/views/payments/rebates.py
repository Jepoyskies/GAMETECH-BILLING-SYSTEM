from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
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
    MessageTemplate,
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar
from billing.views import calculate_new_expiration_date


@login_required
@permission_required("billing.add_rebate", raise_exception=True)
def customer_rebate_view(request, username):
    # Depending on how Antigravity named your field, it might be 'username' or 'pppoe_username'
    customer = get_object_or_404(Customer, pppoe_username=username)

    if request.method == "POST":
        new_expiry_str = request.POST.get("new_due_date_time")
        note = request.POST.get("note")

        if new_expiry_str:
            # Convert HTML datetime-local string to timezone-aware Python datetime
            new_expiry = timezone.datetime.fromisoformat(new_expiry_str)
            if timezone.is_naive(new_expiry):
                new_expiry = timezone.make_aware(new_expiry)

            old_expiry = customer.expires_at

            # 1. Update Customer Expiry
            customer.expires_at = new_expiry
            # customer.sms_sent_at = None  # TODO: Uncomment when SMS is added

            # Dynamic Status Update based on rebate time
            was_suspended = customer.status in ["suspended", "inactive", "expired"]
            if new_expiry <= timezone.now() and customer.status == "active":
                customer.status = "expired"
            elif new_expiry > timezone.now() and was_suspended:
                customer.status = "active"

            customer.save()

            # 2. Log the Rebate
            from billing.models import Rebate

            Rebate.objects.create(
                customer=customer,
                username=customer.pppoe_username,
                plan_name=customer.plan.name if customer.plan else None,
                current_expiry=old_expiry,
                expires_at=new_expiry,
                note=note,
                adjusted_by=request.user.username,
            )

            # 2.5 Update SLA Rebates Given if this was an SLA rebate
            ticket_id = request.POST.get("ticket_id")
            if ticket_id:
                from dispatch.models import DispatchRecord

                try:
                    ticket = DispatchRecord.objects.get(id=ticket_id, customer=customer)
                    # For simplicity, if manual rebate is given for a ticket, we just mark the current owed_days
                    delta = timezone.now() - ticket.created_at
                    hours_open = delta.total_seconds() / 3600
                    owed_days = int(hours_open // 24)
                    if owed_days > ticket.sla_rebates_given:
                        ticket.sla_rebates_given = owed_days
                        ticket.save()
                except Exception:
                    pass

            # 3. Sync to Mikrotik — kick/reactivate as needed based on new expiry
            if customer.mikrotik_device and customer.pppoe_username:
                try:
                    from network_manager.services import MikrotikAPI

                    api = MikrotikAPI(customer.mikrotik_device)
                    if customer.status == "active":
                        # Reactivate if they were suspended before
                        api.enable_pppoe_user(customer.pppoe_username)
                        if customer.plan and customer.plan.name:
                            api.set_user_pppoe_profile(
                                customer.pppoe_username, customer.plan.name
                            )
                    api.kick_active_user(customer.pppoe_username)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        f"Rebate Mikrotik sync failed for {customer.pppoe_username}: {e}"
                    )

            # 4. Pass data to success page for copying
            context = {
                "customer": customer,
                "new_expiry": new_expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "adjusted_by": request.user.username,
                "action_type": "Rebate",
                "amount": "0.00",
            }
            return render(request, "billing/payment_success.html", context)

    # Check for SLA breaches
    from dispatch.models import DispatchRecord
    import datetime

    open_tickets = DispatchRecord.objects.filter(
        done_at__isnull=True, customer=customer
    )
    sla_breaches = []

    for ticket in open_tickets:
        delta = timezone.now() - ticket.created_at
        hours_open = delta.total_seconds() / 3600
        if hours_open >= 24:
            owed_days = int(hours_open // 24)
            if owed_days > ticket.sla_rebates_given:
                sla_breaches.append(
                    {
                        "ticket_id": ticket.id,
                        "hours_open": int(hours_open),
                        "owed_days": owed_days - ticket.sla_rebates_given,
                        "concern": ticket.concern,
                    }
                )

    context = {
        "customer": customer,
        "current_expiry_js": (
            customer.expires_at.strftime("%Y-%m-%dT%H:%M:%S")
            if customer.expires_at
            else timezone.now().strftime("%Y-%m-%dT%H:%M:%S")
        ),
        "sla_breaches": sla_breaches,
    }
    return render(request, "billing/customer_rebate.html", context)


@login_required
@permission_required("billing.add_rollback", raise_exception=True)
def customer_rollback_view(request, username):
    customer = get_object_or_404(Customer, pppoe_username=username)

    if request.method == "POST":
        rollback_to_str = request.POST.get("rollback_to")
        note = request.POST.get("note")
        rollback_amount_str = request.POST.get("rollback_amount", "0")

        try:
            from decimal import Decimal

            rollback_amount = Decimal(rollback_amount_str)
        except Exception:
            rollback_amount = Decimal("0.00")

        if rollback_to_str:
            new_expiry = timezone.datetime.fromisoformat(rollback_to_str)
            if timezone.is_naive(new_expiry):
                new_expiry = timezone.make_aware(new_expiry)

            old_expiry = customer.expires_at

            # 1. Update Customer Expiry (Rollback) & Balance
            customer.expires_at = new_expiry
            if rollback_amount > 0:
                customer.outstanding_balance += rollback_amount

            # 1.b Dynamic Status Update based on rollback time
            was_suspended = customer.status in ["suspended", "inactive", "expired"]
            if new_expiry <= timezone.now() and customer.status == "active":
                customer.status = "expired"
            elif new_expiry > timezone.now() and was_suspended:
                customer.status = "active"

            customer.save()

            # 2. Log the Rollback (Rebate model)
            from billing.models import Rebate, Payment

            Rebate.objects.create(
                customer=customer,
                username=customer.pppoe_username,
                plan_name=customer.plan.name if customer.plan else None,
                current_expiry=old_expiry,
                expires_at=new_expiry,
                amount=rollback_amount,
                note=f"Rollback: {note}",
                adjusted_by=request.user.username,
            )

            # 3. Create a negative payment record so it reflects accurately in ledger
            if rollback_amount > 0:
                Payment.objects.create(
                    customer=customer,
                    username=customer.pppoe_username,
                    plan_name=customer.plan.name if customer.plan else None,
                    amount=-rollback_amount,
                    payment_method="Rollback",
                    reason=f"Rollback: {note}",
                    adjusted_by=request.user.username,
                    paid_at=timezone.now(),
                )

            # 4. Sync to Mikrotik — kick/suspend as needed based on reverted expiry
            if customer.mikrotik_device and customer.pppoe_username:
                try:
                    from network_manager.services import MikrotikAPI

                    api = MikrotikAPI(customer.mikrotik_device)
                    if customer.status == "active":
                        api.enable_pppoe_user(customer.pppoe_username)
                        if customer.plan and customer.plan.name:
                            api.set_user_pppoe_profile(
                                customer.pppoe_username, customer.plan.name
                            )
                    api.kick_active_user(customer.pppoe_username)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        f"Rollback Mikrotik sync failed for {customer.pppoe_username}: {e}"
                    )

            context = {
                "customer": customer,
                "new_expiry": new_expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "adjusted_by": request.user.username,
                "action_type": (
                    "Rollback Expiry & Amount"
                    if rollback_amount > 0
                    else "Rollback Expiry"
                ),
                "amount": str(rollback_amount),
            }
            return render(request, "billing/payment_success.html", context)

    context = {
        "customer": customer,
        "current_expiry_js": (
            customer.expires_at.strftime("%Y-%m-%dT%H:%M")
            if customer.expires_at
            else ""
        ),
    }
    return render(request, "billing/customer_rollback.html", context)
