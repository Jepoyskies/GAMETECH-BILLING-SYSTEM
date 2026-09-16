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
from decimal import Decimal, InvalidOperation
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


@login_required
def subscription_plans_view(request):
    """Customer Subscriptions Dashboard Skeleton View."""
    search = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "")
    device_filter = request.GET.get("device", "")
    connection_filter = request.GET.get("connection", "")
    per_page = int(request.GET.get("per_page", 10))
    sort = request.GET.get("sort", "expires_at")
    order = request.GET.get("order", "desc").lower()

    unique_devices = (
        Customer.objects.filter(mikrotik_device__isnull=False)
        .values_list("mikrotik_device__device_name", flat=True)
        .distinct()
    )

    context = {
        "search": search,
        "status_filter": status_filter,
        "device_filter": device_filter,
        "connection_filter": connection_filter,
        "per_page": per_page,
        "sort": sort,
        "order": order.upper(),
        "unique_devices": unique_devices,
    }
    return render(request, "billing/subscription_plans.html", context)


def plan_list(request):
    if hasattr(request.user, "role") and request.user.role == "Agent":
        return redirect("customer_list")

    all_plans = SubscriptionPlan.objects.all().order_by("price")

    # Categorize plans based on their names
    categorized_plans = {
        "Legacy Plans": [],
        "GTipid Fiber": [],
        "GIMI Home Fiber": [],
        "SME Business Plans": [],
        "Enterprise Plan": [],
        "Other Plans": [],
    }

    for plan in all_plans:
        name_lower = plan.name.lower()
        if "legacy" in name_lower or plan.name in ["5Mbps", "10Mbps"]:
            categorized_plans["Legacy Plans"].append(plan)
        elif "gtipid" in name_lower:
            categorized_plans["GTipid Fiber"].append(plan)
        elif "gimi home" in name_lower:
            categorized_plans["GIMI Home Fiber"].append(plan)
        elif "sme" in name_lower:
            categorized_plans["SME Business Plans"].append(plan)
        elif "enterprise" in name_lower:
            categorized_plans["Enterprise Plan"].append(plan)
        else:
            categorized_plans["Other Plans"].append(plan)

    # Filter out empty categories
    active_categories = {k: v for k, v in categorized_plans.items() if v}

    return render(
        request, "billing/service_plans.html", {"grouped_plans": active_categories}
    )


@login_required
def sync_plans_from_mikrotik(request):
    from network_manager.models import MikrotikDevice
    from network_manager.services import MikrotikAPI
    import re

    device = MikrotikDevice.objects.first()
    if not device:
        messages.error(request, "No active MikroTik device found for sync.")
        return redirect("plan_list")

    try:
        api = MikrotikAPI(device)
        router_api = api._get_api()
        profiles = router_api.get_resource("/ppp/profile").get()
        api.connection.disconnect()

        synced_count = 0
        ignored_profiles = ["default", "expired", "default-encryption"]

        for p in profiles:
            name = p.get("name")
            if name in ignored_profiles:
                continue

            rate_limit = p.get("rate-limit", "")
            speed_up = "1 Mbps"
            speed_down = "1 Mbps"

            if rate_limit:
                parts = rate_limit.split("/")
                if len(parts) == 2:
                    # convert 10M to 10 Mbps
                    def format_speed(s):
                        s = s.upper()
                        if "M" in s:
                            return f"{s.replace('M', '')} Mbps"
                        if "K" in s:
                            return f"{s.replace('K', '')} Kbps"
                        if "G" in s:
                            return f"{s.replace('G', '')} Gbps"
                        return f"{s} bps"

                    speed_up = format_speed(parts[0])
                    speed_down = format_speed(parts[1])

            # Create or update plan
            plan, created = SubscriptionPlan.objects.get_or_create(
                name=name,
                defaults={
                    "speed_up": speed_up,
                    "speed_down": speed_down,
                    "price": 0.00,
                    "validity_days": 30,
                },
            )
            if not created:
                plan.speed_up = speed_up
                plan.speed_down = speed_down
                plan.save()

            synced_count += 1

        messages.success(
            request, f"Successfully synced {synced_count} profiles from MikroTik."
        )
    except Exception as e:
        messages.error(request, f"MikroTik API Error during sync: {str(e)}")

    return redirect("plan_list")


@role_required(["Admin", "Editor"])
@login_required
def add_plan(request):
    if request.method == "POST":
        name = request.POST.get("plan_name")
        speed_up = request.POST.get("speed_up")
        speed_down = request.POST.get("speed_down")
        price = request.POST.get("price")
        validity_days = request.POST.get("validity_days")
        description = request.POST.get("description")

        SubscriptionPlan.objects.create(
            name=name,
            speed_up=speed_up,
            speed_down=speed_down,
            price=price,
            validity_days=validity_days,
            description=description,
        )
        messages.success(request, f"Service plan '{name}' added successfully!")
        return redirect("plan_list")

    return render(request, "billing/add_plan.html")


@role_required(["Admin", "Editor"])
@login_required
def edit_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    if request.method == "POST":
        plan.name = request.POST.get("plan_name")
        plan.speed_up = request.POST.get("speed_up")
        plan.speed_down = request.POST.get("speed_down")
        plan.price = request.POST.get("price")
        plan.validity_days = request.POST.get("validity_days")
        plan.description = request.POST.get("description")
        plan.save()

        messages.success(request, "Service plan updated successfully!")
        return redirect("plan_list")

    return render(request, "billing/edit_plan.html", {"plan": plan})


@role_required(["Admin", "Editor"])
@login_required
def delete_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    plan.delete()
    messages.success(request, "Service plan deleted successfully!")
    return redirect("plan_list")


@login_required
def cignal_play_list_view(request):
    search = request.GET.get("search", "")
    status_filter = request.GET.get("status", "all")

    customers = Customer.objects.filter(
        (Q(cignalplay_no__isnull=False) & ~Q(cignalplay_no__exact=""))
        | (Q(cignalbox_no__isnull=False) & ~Q(cignalbox_no__exact=""))
    )

    if search:
        customers = customers.filter(
            Q(full_name__icontains=search)
            | Q(username__icontains=search)
            | Q(cignalplay_no__icontains=search)
            | Q(cignalbox_no__icontains=search)
            | Q(cignalplay_adjustedby__icontains=search)
            | Q(cignalbox_adjustedby__icontains=search)
        )

    customers = customers.order_by("-created_at")

    # We will pass this to template and handle basic status filtering in Python if needed,
    # but for now let's just pass the raw customers.
    paginator = Paginator(customers, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search": search,
        "status_filter": status_filter,
    }

    q = request.GET.copy()
    if "page" in q:
        del q["page"]
    context["query_params"] = q.urlencode()
    return render(request, "billing/cignal_play_list.html", context)


@login_required
def add_on_payments_view(request):
    search = request.GET.get("search", "")

    # Very similar to cignal_play_list but might show all with add-on plans in CignalPlay table
    customers_with_addons = Customer.objects.filter(
        cignal_plans__isnull=False
    ).distinct()

    if search:
        customers_with_addons = customers_with_addons.filter(
            Q(full_name__icontains=search)
            | Q(username__icontains=search)
            | Q(cignalplay_no__icontains=search)
        )

    customers_with_addons = customers_with_addons.order_by("-created_at")

    paginator = Paginator(customers_with_addons, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Fetch all active customers for Walk-in Payment dropdown
    all_customers = Customer.objects.filter(status="active").values(
        "pppoe_username", "full_name"
    )

    context = {
        "page_obj": page_obj,
        "search": search,
        "all_customers": all_customers,
    }

    q = request.GET.copy()
    if "page" in q:
        del q["page"]
    context["query_params"] = q.urlencode()
    return render(request, "billing/add_on_payments.html", context)


@login_required
def cignalplay_form_view(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == "POST":
        plan_name = request.POST.get("plan_name")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        adjusted_by = request.POST.get("adjusted_by")

        CignalPlay.objects.create(
            customer=customer,
            plan_name=plan_name,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            adjusted_by=adjusted_by,
        )

        # Also update the customer's cignalplay_adjustedby field
        customer.cignalplay_adjustedby = adjusted_by
        customer.save()

        Notification.objects.create(
            title="Cignal Play / Add-on Applied",
            message=f"{customer.full_name} applied for {plan_name}.",
            notification_type="cignal",
            link=f"/customer/{customer.id}/cignal-logs/",
        )

        messages.success(
            request,
            f"Successfully recorded Cignal Play / Add-on payment for {customer.full_name}.",
        )
        return redirect("user_cignal_logs", customer_id=customer.id)

    context = {"customer": customer}
    return render(request, "billing/cignalplay_form.html", {"form": form})


def get_categorized_plans():
    all_plans = SubscriptionPlan.objects.all().order_by("price")
    categorized_plans = {
        "Legacy Plans": [],
        "GTipid Fiber": [],
        "GIMI Home Fiber": [],
        "SME Business Plans": [],
        "Enterprise Plan": [],
        "Other Plans": [],
    }
    for plan in all_plans:
        name_lower = plan.name.lower()
        if "legacy" in name_lower or plan.name in ["5Mbps", "10Mbps"]:
            categorized_plans["Legacy Plans"].append(plan)
        elif "gtipid" in name_lower:
            categorized_plans["GTipid Fiber"].append(plan)
        elif "gimi home" in name_lower:
            categorized_plans["GIMI Home Fiber"].append(plan)
        elif "sme" in name_lower:
            categorized_plans["SME Business Plans"].append(plan)
        elif "enterprise" in name_lower:
            categorized_plans["Enterprise Plan"].append(plan)
        else:
            categorized_plans["Other Plans"].append(plan)
    return {k: v for k, v in categorized_plans.items() if v}


@login_required
def user_cignal_logs_view(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    logs = customer.cignal_plans.all()

    context = {"customer": customer, "logs": logs}
    return render(request, "billing/user_cignal_logs.html", context)


@login_required
@transaction.atomic
def apply_cignal_addon(request):
    if request.method == "POST":
        request_id = request.POST.get("request_id")
        customer_id = request.POST.get("customer_id")
        cignal_play_no = (
            request.POST.get("cignal_play_no", "").strip()
            or request.POST.get("cignalplay_no", "").strip()
        )
        cignal_box_no = (
            request.POST.get("cignal_box_no", "").strip()
            or request.POST.get("cignalbox_no", "").strip()
        )
        cignalplay_date_raw = request.POST.get("cignalplay_date")
        expiration_date_raw = request.POST.get("expiration_date") or request.POST.get("new_expiration_date")
        account_name = (
            request.POST.get("account_name", "").strip()
            or request.POST.get("label", "").strip()
        )
        payment_method = request.POST.get("payment_method", "Cash").strip()
        reference_no = request.POST.get("reference_no", "").strip()
        notes = request.POST.get("notes", "").strip() or request.POST.get("remarks", "").strip()

        # Validate at least one account number is present
        if not cignal_play_no and not cignal_box_no:
            messages.error(request, "Please provide at least one Cignal account number (Play No. or Box No.).")
            return redirect(request.META.get("HTTP_REFERER", "cignal_dashboard"))

        # Parse initial payment amount
        initial_amount_raw = request.POST.get("initial_amount") or request.POST.get("amount") or "0"
        try:
            initial_amount = Decimal(str(initial_amount_raw).replace(",", "").strip())
        except (InvalidOperation, ValueError, TypeError):
            initial_amount = Decimal("0.00")

        customer = get_object_or_404(Customer, id=customer_id)

        # Parse activation datetime
        now = timezone.localtime()
        if cignalplay_date_raw:
            try:
                act_d = datetime.fromisoformat(cignalplay_date_raw).date()
                activation_dt = timezone.make_aware(datetime.combine(act_d, now.time()))
            except (ValueError, TypeError):
                activation_dt = now
        else:
            activation_dt = now

        # Parse First Due Date / Expiration Datetime
        if expiration_date_raw:
            try:
                exp_d = datetime.fromisoformat(expiration_date_raw).date()
                expiration_dt = timezone.make_aware(datetime.combine(exp_d, datetime.max.time().replace(microsecond=0)))
            except (ValueError, TypeError):
                expiration_dt = activation_dt + timedelta(days=30)
        else:
            expiration_dt = activation_dt + timedelta(days=30)

        # Resolve pending request if provided
        if request_id:
            try:
                addon_req = AddOnRequest.objects.get(id=request_id)
                addon_req.status = "Resolved"
                addon_req.save()
            except AddOnRequest.DoesNotExist:
                pass
        else:
            # Auto-resolve open pending Cignal request for this customer
            pending_req = (
                AddOnRequest.objects.filter(customer=customer, status="Pending")
                .filter(Q(addon_type__icontains="Cignal") | Q(addon_type__icontains="Box"))
                .order_by("-requested_at")
                .first()
            )
            if pending_req:
                pending_req.status = "Resolved"
                pending_req.save()

        # Update customer profile summary fields
        if cignal_play_no:
            customer.cignalplay_no = cignal_play_no
            customer.cignalplay_date = activation_dt
            customer.cignalplay_adjustedby = request.user.username
        if cignal_box_no:
            customer.cignalbox_no = cignal_box_no
            customer.cignalbox_date = activation_dt
            customer.cignalbox_adjustedby = request.user.username
        customer.save()

        # Format account numbers summary
        account_nos = []
        if cignal_play_no:
            account_nos.append(f"Play: {cignal_play_no}")
        if cignal_box_no:
            account_nos.append(f"Box: {cignal_box_no}")
        acct_summary = " | ".join(account_nos)
        sub_name = account_name or f"Cignal - {acct_summary}"

        # Parse hardware & load plan selections
        hardware_payment_type = request.POST.get("hardware_payment_type", "none").strip()
        monthly_load_plan = request.POST.get("monthly_load_plan", "149").strip()
        if hardware_payment_type == "cashout":
            installments_paid = 12
        elif hardware_payment_type == "installment":
            installments_paid = 1
        else:
            installments_paid = 0

        # Create CignalPlay subscription record (Unified)
        subscription = CignalPlay.objects.create(
            customer=customer,
            plan_name="Cignal Subscription",
            account_name=sub_name,
            cignal_play_no=cignal_play_no,
            cignal_box_no=cignal_box_no,
            start_date=activation_dt,
            expiration_date=expiration_dt,
            end_date=expiration_dt,
            amount_paid=initial_amount,
            hardware_payment_type=hardware_payment_type,
            installments_paid=installments_paid,
            monthly_load_plan=monthly_load_plan,
            adjusted_by=request.user.username,
        )

        # Crucial: Automatically generate a Payment record for the Initial Payment Amount
        if initial_amount > 0:
            acct_desc = subscription.account_name or acct_summary
            hw_desc = f"Hardware: {hardware_payment_type.title()}" if hardware_payment_type != "none" else "App Only"
            reason_text = f"Cignal Activation: {acct_desc} ({hw_desc} + {monthly_load_plan} Load)"
            if notes:
                reason_text += f" | {notes}"

            Payment.objects.create(
                customer=customer,
                username=customer.pppoe_username or customer.full_name,
                plan_name="Cignal Subscription",
                amount=initial_amount,
                payment_method=payment_method or "Cash",
                reference_no=reference_no or f"ACT-{customer.id}-{subscription.id}",
                reason=reason_text,
                expires_at=expiration_dt or customer.expires_at,
                paid_at=timezone.now(),
                payment_date_received=timezone.now(),
                adjusted_by=request.user.username,
            )

            audit_notes = f" | Notes: {notes}" if notes else ""
            AuditLog.objects.create(
                admin_user=request.user,
                customer=customer,
                action_type="Cignal Activation Payment",
                remarks=f"Initial Payment: ₱{initial_amount:,.2f} | {hw_desc} ({installments_paid}/12 paid) | Load Plan: ₱{monthly_load_plan} | Ref: {reference_no or 'N/A'}{audit_notes} | Due Date: {expiration_dt.strftime('%Y-%m-%d')} | Accounts: {acct_summary}",
            )

        # Notification
        pay_info = f" with initial payment ₱{initial_amount:,.2f}" if initial_amount > 0 else ""
        Notification.objects.create(
            title="Cignal Subscription Activated",
            message=f"{customer.full_name} activated Cignal Subscription ({sub_name}){pay_info} by {request.user.username}. Due: {expiration_dt.strftime('%b %d, %Y')}.",
            notification_type="cignal",
            link=f"/customer/{customer.id}/cignal-logs/",
        )

        success_msg = f"Cignal Subscription activated successfully for {customer.full_name} ({acct_summary})!"
        if initial_amount > 0:
            success_msg += f" Initial payment of ₱{initial_amount:,.2f} recorded (Due: {expiration_dt.strftime('%b %d, %Y')})."
        messages.success(request, success_msg)

    return redirect(request.META.get("HTTP_REFERER", "cignal_dashboard"))


@role_required(["Admin", "Editor", "Technician", "Agent"])
@login_required
@require_POST
def approve_cignal_request(request, request_id):
    from billing.models import AddOnRequest

    addon_req = get_object_or_404(AddOnRequest, pk=request_id)
    cignal_no = request.POST.get("cignal_play_no") or request.POST.get("cignal_no")
    cignal_date = request.POST.get("cignal_date")
    if not cignal_no or not cignal_date:
        messages.error(request, "Cignal Account No and Date are required.")
        return redirect(request.META.get("HTTP_REFERER", "cignal_dashboard"))
    customer = addon_req.customer
    is_box = "box" in (addon_req.addon_type or "").lower()
    if is_box:
        customer.cignalbox_no = cignal_no
        customer.cignalbox_adjustedby = request.user.username
        try:
            customer.cignalbox_date = timezone.datetime.fromisoformat(cignal_date).date()
        except ValueError:
            customer.cignalbox_date = timezone.now()
    else:
        customer.cignalplay_no = cignal_no
        customer.cignalplay_adjustedby = request.user.username
        try:
            customer.cignalplay_date = timezone.datetime.fromisoformat(cignal_date).date()
        except ValueError:
            customer.cignalplay_date = timezone.now()
    customer.save()
    addon_req.status = "Resolved"
    addon_req.save()
    messages.success(
        request, f"Cignal request for {customer.full_name} approved and applied."
    )
    return redirect(request.META.get("HTTP_REFERER", "cignal_dashboard"))
