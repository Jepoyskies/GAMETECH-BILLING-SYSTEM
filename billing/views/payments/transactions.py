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
def create_payment_view(request, customer_id):
    from django.shortcuts import get_object_or_404

    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == "POST":
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        amount = request.POST.get("amount")
        payment_method = request.POST.get("payment_method")
        reference_no = request.POST.get("reference_no")
        payment_date_received = request.POST.get("payment_date_received")
        reason = request.POST.get("reason")

        # Calculate days paid
        try:
            # Simple handling if provided in YYYY-MM-DDTHH:MM:SS format
            sd = (
                datetime.fromisoformat(start_date.replace("Z", ""))
                if start_date
                else timezone.now()
            )
            ed = (
                datetime.fromisoformat(end_date.replace("Z", ""))
                if end_date
                else timezone.now()
            )

            # ensure aware datetime
            if timezone.is_naive(sd):
                sd = timezone.make_aware(sd)
            if timezone.is_naive(ed):
                ed = timezone.make_aware(ed)

            days_paid = round((ed - sd).total_seconds() / (24 * 3600), 4)
        except Exception as e:
            print("Date parse err:", e)
            days_paid = 0
            ed = timezone.now()

        try:
            pdr = datetime.fromisoformat(payment_date_received.replace("Z", ""))
            if timezone.is_naive(pdr):
                pdr = timezone.make_aware(pdr)
        except Exception:
            pdr = timezone.now()

        Payment.objects.create(
            customer=customer,
            username=customer.pppoe_username or customer.full_name,
            plan_name=customer.plan.name if customer.plan else "",
            mikrotik_device_name=(
                customer.mikrotik_device.device_name if customer.mikrotik_device else ""
            ),
            amount=amount,
            days_paid=days_paid,
            payment_method=payment_method,
            reference_no=reference_no,
            reason=reason,
            expires_at=ed,
            payment_date_received=pdr,
            paid_at=timezone.now(),
            adjusted_by=(
                request.user.username if request.user.is_authenticated else "system"
            ),
        )

        customer.expires_at = ed

        # If the customer was previously inactive or suspended, auto-reactivate them
        if customer.status in ["expired", "suspended", "inactive", "past_due"]:
            customer.status = "active"

        customer.save()

        messages.success(
            request,
            f"Payment for {customer.pppoe_username or customer.full_name} processed successfully.",
        )
        return redirect("payment_logs")

    return render(request, "billing/pay.html", {"customer": customer})


@login_required
@permission_required("billing.add_payment", raise_exception=True)
def pay_customer_view(request, username):
    customer = get_object_or_404(Customer, pppoe_username=username)

    # Calculate Monthly Price
    monthly_price = float(customer.plan.price) if customer.plan else 0.0

    # Capture dynamic redirect URL
    next_url = (
        request.GET.get("next")
        or request.POST.get("next_url")
        or request.META.get("HTTP_REFERER")
        or reverse("payment_portal")
    )

    if request.method == "POST":
        start_date_str = request.POST.get("start_date")
        amount = request.POST.get("amount")
        payment_method = request.POST.get("payment_method")
        reference_no = request.POST.get("reference_no", "")
        reason = request.POST.get("reason", "")
        new_plan_id = request.POST.get("new_plan_id")

        if amount:
            from decimal import Decimal

            amount_float = float(amount)

            # Determine baseline current expiration
            if start_date_str:
                current_exp = timezone.datetime.fromisoformat(
                    start_date_str.replace("Z", "")
                )
                if timezone.is_naive(current_exp):
                    current_exp = timezone.make_aware(current_exp)
            elif customer.expires_at and customer.expires_at > timezone.now():
                current_exp = customer.expires_at
            else:
                current_exp = timezone.now()

            with transaction.atomic():
                # Lock the customer row for atomic update
                locked_customer = Customer.objects.select_for_update().get(
                    pk=customer.pk
                )

                # --- UPGRADE PLAN LOGIC ---
                is_upgrade = False
                is_downgrade = False
                old_plan_name = (
                    locked_customer.plan.name if locked_customer.plan else "None"
                )

                if new_plan_id and str(locked_customer.plan_id) != str(new_plan_id):
                    new_plan = SubscriptionPlan.objects.filter(id=new_plan_id).first()
                    if new_plan:
                        old_price = (
                            float(locked_customer.plan.price)
                            if locked_customer.plan
                            else 0.0
                        )
                        monthly_price = float(new_plan.price)
                        locked_customer.plan = new_plan
                        if monthly_price > old_price:
                            is_upgrade = True
                        else:
                            is_downgrade = True
                        locked_customer.save()  # Triggers Mikrotik Sync
                # --------------------------

                # --- Option B: Wallet/Advance Payment Logic ---
                amount_for_time = amount_float

                # Calculate new expiration using ONLY the amount meant for time
                new_expiry = calculate_new_expiration_date(
                    current_exp, amount_for_time, monthly_price
                )

                was_suspended = locked_customer.status in [
                    "suspended",
                    "inactive",
                    "expired",
                ]

                # 1. Update Customer Expiry
                locked_customer.expires_at = new_expiry

                # 2. Deduct from outstanding balance
                locked_customer.outstanding_balance -= Decimal(amount)

                # 3. Update Status if suspended
                if was_suspended:
                    locked_customer.status = "active"

                locked_customer.save()

                # Capture was_suspended AFTER save so Mikrotik block outside uses locked state
                _was_suspended_for_mikrotik = was_suspended

                # 4. Log the Payment
                payment = Payment.objects.create(
                    customer=locked_customer,
                    username=locked_customer.pppoe_username,
                    plan_name=(
                        locked_customer.plan.name if locked_customer.plan else None
                    ),
                    amount=amount,
                    payment_method=payment_method,
                    reference_no=reference_no,
                    reason=reason,
                    expires_at=new_expiry,
                    adjusted_by=request.user.username,
                    paid_at=timezone.now(),
                )

                # Send Notification
                Notification.objects.create(
                    title=f"Payment Received: ₱{amount}",
                    message=f"{locked_customer.full_name} paid via {payment_method}.",
                    notification_type="payment",
                    link=f"/logs/payments/",
                )

            # Process User Notifications (SMS/Email)
            send_sms = request.POST.get("send_sms") == "on"
            send_email = request.POST.get("send_email") == "on"

            if send_sms or send_email:
                context = {
                    "{customer_name}": customer.full_name,
                    "{paid_amount}": str(amount),
                    "{new_expiration}": (
                        new_expiry.strftime("%Y-%m-%d %H:%M") if new_expiry else ""
                    ),
                }

                if send_sms and customer.phone:
                    template_sms = MessageTemplate.objects.filter(type="SMS").first()
                    if template_sms:
                        msg = template_sms.body
                        for k, v in context.items():
                            msg = msg.replace(k, str(v))
                        from billing.views import send_semaphore_sms

                        res, success = send_semaphore_sms(customer.phone, msg)
                        SmsLog.objects.create(
                            phone=customer.phone,
                            message=msg,
                            status="Sent" if success else "Failed",
                            response=res,
                        )

                if send_email and customer.email:
                    template_email = MessageTemplate.objects.filter(
                        type="EMAIL"
                    ).first()
                    if template_email:
                        subj = template_email.subject or "Payment Confirmation"
                        msg = template_email.body
                        for k, v in context.items():
                            subj = subj.replace(k, str(v))
                            msg = msg.replace(k, str(v))
                        try:
                            from django.core.mail import send_mail

                            send_mail(
                                subj,
                                msg,
                                settings.DEFAULT_FROM_EMAIL,
                                [customer.email],
                                fail_silently=False,
                            )
                        except Exception as e:
                            print(f"Email failed: {e}")

            # 5. Mikrotik API Reactivation
            if customer.mikrotik_device:
                try:
                    from network_manager.services import MikrotikAPI

                    api = MikrotikAPI(customer.mikrotik_device)

                    # Use the was_suspended flag captured from the locked_customer inside the atomic block
                    _ws = locals().get("_was_suspended_for_mikrotik", was_suspended)

                    if _ws:
                        # 1. Enable the user (Removes bridge drop and enables secret)
                        api.enable_pppoe_user(customer.pppoe_username)
                        # 2. Update the profile back to their plan, or default if none
                        target_profile = (
                            customer.plan.name
                            if customer.plan and customer.plan.name
                            else "default"
                        )
                        api.set_user_pppoe_profile(
                            customer.pppoe_username, target_profile
                        )
                        # 3. Kick them so they reconnect and get the new profile
                        api.kick_active_user(customer.pppoe_username)
                    else:
                        # Even if not previously suspended, kick so router updates comment/profile
                        api.kick_active_user(customer.pppoe_username)
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Failed to sync renewal for {customer.pppoe_username} on MikroTik: {e}"
                    )

            # 4. Success Output

            # Generate Text Template
            template_text = MessageTemplate.objects.filter(type="TEXT").first()
            if template_text:
                messenger_msg = template_text.body
                context_replacements = {
                    "{customer_name}": customer.full_name,
                    "{paid_amount}": str(amount),
                    "{new_expiration}": (
                        new_expiry.strftime("%B %d, %Y") if new_expiry else ""
                    ),
                }
                for k, v in context_replacements.items():
                    messenger_msg = messenger_msg.replace(k, str(v))
            else:
                messenger_msg = f"Hi {customer.full_name},\n\nThank you for your payment of ₱{amount} via {payment_method}. Your internet connection is now active until {new_expiry.strftime('%B %d, %Y')}."
                if is_upgrade:
                    messenger_msg += f"\n\nThank you for upgrading to {new_plan.name}! Enjoy your faster speeds."
                elif is_downgrade:
                    messenger_msg += f"\n\nYour plan has been successfully updated to {new_plan.name}. If you wish to upgrade soon for faster speeds, you can always let us know!"

            context = {
                "customer": customer,
                "new_expiry": new_expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "adjusted_by": request.user.username,
                "action_type": "Standard Renewal",
                "amount": amount,
                "next_url": next_url,
                "messenger_template": messenger_msg,
            }
            return render(request, "billing/payment_success.html", context)

    # GET Request: Setup defaults
    current_expiry = customer.expires_at or timezone.now()
    start_default_str = current_expiry.strftime("%Y-%m-%dT%H:%M:%S")

    # Add roughly one month for the default end date
    end_default = current_expiry + timezone.timedelta(days=30)
    end_default_str = end_default.strftime("%Y-%m-%dT%H:%M:%S")

    plans = SubscriptionPlan.objects.all().order_by("price")

    context = {
        "customer": customer,
        "plans": plans,
        "current_expiry_display": current_expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "start_default_str": start_default_str,
        "end_default_str": end_default_str,
        "monthly_price": monthly_price,
        "next_url": next_url,
    }
    return render(request, "billing/pay_customer.html", context)


@login_required
def payment_portal_view(request):
    """A centralized dashboard for cashiers to search and select a customer to pay."""
    customers = Customer.objects.select_related("plan").all().order_by("-created_at")
    return render(request, "billing/payment_portal.html", {"customers": customers})


@login_required
def payment_success_view(request):
    """Fallback view if someone accesses the URL directly"""
    return redirect("customer_list")
