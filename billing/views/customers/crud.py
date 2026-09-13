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
@role_required(["Admin", "Agent", "CSR"])
@permission_required("billing.add_customer", raise_exception=True)
def add_customer(request):
    if request.method == "POST":
        from django.utils.crypto import get_random_string

        if request.user.role == "Agent":
            barangay_name = request.POST.get("barangay_name")
            if barangay_name:
                barangay, _ = Barangay.objects.get_or_create(
                    name__iexact=barangay_name,
                    defaults={"name": barangay_name, "health_status": "Excellent"},
                )
                barangay_id = barangay.id
            else:
                barangay_id = None
            latitude = None
            longitude = None
        else:
            barangay_id = request.POST.get("barangay_id")
            latitude = request.POST.get("latitude") or None
            longitude = request.POST.get("longitude") or None

        customer = Customer.objects.create(
            full_name=request.POST.get("full_name"),
            email=request.POST.get("email") or None,
            phone=request.POST.get("phone"),
            address=request.POST.get("address"),
            pppoe_username=request.POST.get("pppoe_username") or None,
            pppoe_password=request.POST.get("pppoe_password") or get_random_string(8),
            status=(
                "pending"
                if request.user.role == "Agent"
                else request.POST.get("status", "active")
            ),
            plan_id=request.POST.get("plan_id"),
            mikrotik_device_id=request.POST.get("device_id") or None,
            agent_id=request.POST.get("agent_id"),
            barangay_id=barangay_id,
            account_type_id=request.POST.get("account_type_id") or None,
            latitude=latitude,
            longitude=longitude,
            cignalplay_no=request.POST.get("cignalplay_no"),
            cignalplay_date=request.POST.get("cignalplay_date") or None,
            cignalbox_no=request.POST.get("cignalbox_no"),
            cignalbox_date=request.POST.get("cignalbox_date") or None,
            created_form_by=request.user.username,
        )

        from billing.models import SystemLog

        SystemLog.objects.create(
            table_name="Customer",
            record_id=str(customer.id),
            action="ADD",
            changed_by=request.user.username,
            target_name=customer.full_name,
            old_data="",
            new_data=f"Name: {customer.full_name}\nPhone: {customer.phone}\nStatus: {customer.status}",
        )
        messages.success(request, "Customer added successfully!")
        return redirect("customer_list")
    context = {
        "categorized_plans": get_categorized_plans(),
        "devices": MikrotikDevice.objects.all(),
        "agents": Agent.objects.all(),
        "barangays": Barangay.objects.all(),
        "account_types": AccountType.objects.all(),
        "prefill_username": request.GET.get("pppoe_username", ""),
    }
    return render(request, "billing/add_customer.html", context)


@role_required(["Admin", "Editor"])
@login_required
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == "POST":
        old_data = []
        new_data = []

        def check_change(field_name, old_val, new_val):
            # Treat None and empty string as equivalent for logging
            if (old_val or "") != (new_val or ""):
                old_data.append(f"{field_name}: {old_val}")
                new_data.append(f"{field_name}: {new_val}")

        check_change("Name", customer.full_name, request.POST.get("full_name"))
        customer.full_name = request.POST.get("full_name")

        check_change("Email", customer.email, request.POST.get("email"))
        customer.email = request.POST.get("email") or None

        check_change("Phone", customer.phone, request.POST.get("phone"))
        customer.phone = request.POST.get("phone")

        check_change("Address", customer.address, request.POST.get("address"))
        customer.address = request.POST.get("address")

        check_change(
            "PPPoE Username",
            customer.pppoe_username,
            request.POST.get("pppoe_username"),
        )
        customer.pppoe_username = request.POST.get("pppoe_username") or None

        new_password = request.POST.get("pppoe_password")
        if new_password:
            check_change("PPPoE Password", "***", "*** (changed)")
            customer.pppoe_password = new_password
        elif not customer.pppoe_password:
            from django.utils.crypto import get_random_string

            customer.pppoe_password = get_random_string(8)
            check_change("PPPoE Password", "None", "*** (auto-generated)")

        new_status = request.POST.get("status", "active")
        check_change("Status", customer.status, new_status)
        if new_status == "suspended":
            if customer.expires_at:
                check_change(
                    "Expiration",
                    customer.expires_at.strftime("%b %d, %Y %I:%M %p"),
                    "None (Suspended)",
                )
            customer.expires_at = None
        customer.status = new_status

        # Handle ForeignKeys — resolve to human-readable names for clear audit logs
        plan_id = request.POST.get("plan_id")
        if str(customer.plan_id or "") != str(plan_id or ""):
            old_plan_name = customer.plan.name if customer.plan else "None"
            new_plan_name = (
                SubscriptionPlan.objects.filter(pk=plan_id)
                .values_list("name", flat=True)
                .first()
                or "None"
                if plan_id
                else "None"
            )
            old_data.append(f"Plan: {old_plan_name}")
            new_data.append(f"Plan: {new_plan_name}")
        customer.plan_id = plan_id if plan_id else None

        device_id = request.POST.get("device_id")
        if str(customer.mikrotik_device_id or "") != str(device_id or ""):
            customer._original_mikrotik_device_id = customer.mikrotik_device_id
            customer._kick_active_on_transfer = request.POST.get("kick_active_on_transfer", "1") in ["1", "true", "True", "on"]
            old_dev_name = (
                customer.mikrotik_device.device_name
                if customer.mikrotik_device
                else "None"
            )
            new_dev_name = (
                MikrotikDevice.objects.filter(pk=device_id)
                .values_list("device_name", flat=True)
                .first()
                or "None"
                if device_id
                else "None"
            )
            old_data.append(f"Router: {old_dev_name}")
            new_data.append(f"Router: {new_dev_name}")
        customer.mikrotik_device_id = device_id if device_id else None

        if request.POST.get("is_verified") == "True":
            if not customer.is_verified:
                old_data.append("Verified: No")
                new_data.append("Verified: Yes")
                customer.is_verified = True

        agent_id = request.POST.get("agent_id")
        if str(customer.agent_id or "") != str(agent_id or ""):
            old_agent_name = customer.agent.name if customer.agent else "None"
            new_agent_name = (
                Agent.objects.filter(pk=agent_id).values_list("name", flat=True).first()
                or "None"
                if agent_id
                else "None"
            )
            old_data.append(f"Agent: {old_agent_name}")
            new_data.append(f"Agent: {new_agent_name}")
        customer.agent_id = agent_id if agent_id else None

        if request.user.role == "Agent":
            barangay_name = request.POST.get("barangay_name")
            if barangay_name:
                barangay, _ = Barangay.objects.get_or_create(
                    name__iexact=barangay_name,
                    defaults={"name": barangay_name, "health_status": "Excellent"},
                )
                if str(customer.barangay_id or "") != str(barangay.id):
                    old_data.append(
                        f"Barangay: {customer.barangay.name if customer.barangay else 'None'}"
                    )
                    new_data.append(f"Barangay: {barangay.name}")
                customer.barangay_id = barangay.id
            else:
                if customer.barangay_id is not None:
                    old_data.append(
                        f"Barangay: {customer.barangay.name if customer.barangay else 'None'}"
                    )
                    new_data.append(f"Barangay: None")
                customer.barangay_id = None
        else:
            barangay_id = request.POST.get("barangay_id")
            if str(customer.barangay_id or "") != str(barangay_id or ""):
                old_bar_name = customer.barangay.name if customer.barangay else "None"
                new_bar_name = (
                    Barangay.objects.filter(pk=barangay_id)
                    .values_list("name", flat=True)
                    .first()
                    or "None"
                    if barangay_id
                    else "None"
                )
                old_data.append(f"Barangay: {old_bar_name}")
                new_data.append(f"Barangay: {new_bar_name}")
            customer.barangay_id = barangay_id if barangay_id else None

        account_type_id = request.POST.get("account_type_id")
        if str(customer.account_type_id or "") != str(account_type_id or ""):
            old_at_name = (
                customer.account_type.type_name if customer.account_type else "None"
            )
            new_at_name = (
                AccountType.objects.filter(pk=account_type_id)
                .values_list("type_name", flat=True)
                .first()
                or "None"
                if account_type_id
                else "None"
            )
            old_data.append(f"Account Type: {old_at_name}")
            new_data.append(f"Account Type: {new_at_name}")
        customer.account_type_id = account_type_id if account_type_id else None

        if request.user.role != "Agent":
            latitude = request.POST.get("latitude")
            if latitude:
                check_change("Latitude", customer.latitude, latitude)
                customer.latitude = latitude
            longitude = request.POST.get("longitude")
            if longitude:
                check_change("Longitude", customer.longitude, longitude)
                customer.longitude = longitude

        # Cignal Play & Box Integration
        check_change(
            "Cignal Play No", customer.cignalplay_no, request.POST.get("cignalplay_no")
        )
        customer.cignalplay_no = request.POST.get("cignalplay_no")

        cignal_date = request.POST.get("cignalplay_date")
        if cignal_date:
            check_change(
                "Cignal Play Date",
                str(customer.cignalplay_date) if customer.cignalplay_date else None,
                cignal_date,
            )
            customer.cignalplay_date = cignal_date

        check_change(
            "Cignal Box No", customer.cignalbox_no, request.POST.get("cignalbox_no")
        )
        customer.cignalbox_no = request.POST.get("cignalbox_no")

        cignal_box_date = request.POST.get("cignalbox_date")
        if cignal_box_date:
            check_change(
                "Cignal Box Date",
                str(customer.cignalbox_date) if customer.cignalbox_date else None,
                cignal_box_date,
            )
            customer.cignalbox_date = cignal_box_date

        check_change(
            "Health Status",
            customer.health_status,
            request.POST.get("health_status", "Excellent"),
        )
        customer.health_status = request.POST.get("health_status", "Excellent")

        check_change(
            "Health Reason", customer.health_reason, request.POST.get("health_reason")
        )
        customer.health_reason = request.POST.get("health_reason")

        if old_data or new_data:
            from billing.models import SystemLog

            log_action = "UPDATE"
            if len(old_data) == 1:
                field_name = old_data[0].split(":")[0].strip()
                log_action = f"Change {field_name}"
            elif len(old_data) == 2:
                f1 = old_data[0].split(":")[0].strip()
                f2 = old_data[1].split(":")[0].strip()
                log_action = f"Change {f1} & {f2}"

            SystemLog.objects.create(
                table_name="Customer",
                record_id=str(customer.id),
                action=log_action,
                changed_by=request.user.username,
                target_name=customer.full_name,
                old_data="\n".join(old_data),
                new_data="\n".join(new_data),
            )

        customer.save()
        messages.success(
            request, f"Customer {customer.full_name} updated successfully!"
        )
        return redirect("view_customer", customer_id=customer.id)

    context = {
        "customer": customer,
        "categorized_plans": get_categorized_plans(),
        "devices": MikrotikDevice.objects.all(),
        "agents": Agent.objects.all(),
        "barangays": Barangay.objects.all(),
        "account_types": AccountType.objects.all(),
    }
    return render(request, "billing/edit_customer.html", context)


@login_required
def view_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    payments = customer.payments.all().order_by("-paid_at")

    # Try to fetch live MT connection status if they have a router
    mt_status = "Loading..."
    uptime = "Loading..."
    live_mac = "Loading..."
    last_logged_out = "Loading..."
    # Combine logs
    all_logs = []

    # 1. System Logs — pass the raw object so format_log_details can render it properly
    sys_logs = SystemLog.objects.filter(
        record_id=str(customer.id), table_name="Customer"
    ).order_by("-changed_at")
    for log in sys_logs:
        all_logs.append(
            {
                "type": "system",
                "date": log.changed_at,
                "title": log.specific_action,
                "details": log.new_data,
                "user": log.changed_by,
                "log_obj": log,  # pass raw object for format_log_details
            }
        )

    # 2. Payments
    for p in payments:
        all_logs.append(
            {
                "type": "payment",
                "date": p.created_at,
                "title": f"Payment: ₱{p.amount}",
                "details": f"Method: {p.payment_method}",
                "user": "System",
                "log_obj": None,
            }
        )

    # 3. Add-ons / Cignal Play
    addons = AddOnRequest.objects.filter(customer=customer)
    for a in addons:
        all_logs.append(
            {
                "type": "addon",
                "date": a.requested_at,
                "title": f"Add-on: {a.addon_type}",
                "details": f"Status: {a.status}",
                "user": "Customer/System",
                "log_obj": None,
            }
        )

    # 4. Audit Logs (force reactivations etc)
    audit_logs = AuditLog.objects.filter(customer=customer)
    for al in audit_logs:
        all_logs.append(
            {
                "type": "audit",
                "date": al.timestamp,
                "title": f"Action: {al.action_type}",
                "details": al.remarks,
                "user": al.admin_user.username if al.admin_user else "System",
                "log_obj": None,
            }
        )

    # Sort all logs by date descending
    all_logs.sort(key=lambda x: x["date"], reverse=True)

    from billing.utils import get_customer_base_expiration

    reverted_expiration = get_customer_base_expiration(customer)

    # Check for pending Cignal / Add-on requests for prominent highlight
    pending_cignal_addon = (
        AddOnRequest.objects.filter(customer=customer, status="Pending")
        .filter(Q(addon_type__icontains="Cignal") | Q(addon_type__icontains="Box"))
        .order_by("-requested_at")
        .first()
    )

    context = {
        "customer": customer,
        "payments": payments,
        "all_logs": all_logs,
        "reverted_expiration": reverted_expiration,
        "pending_cignal_addon": pending_cignal_addon,
        "mt_status": mt_status,
        "uptime": uptime,
        "live_mac": live_mac,
        "last_logged_out": last_logged_out,
    }
    return render(request, "billing/view_customer.html", context)


@login_required
@role_required(["Admin", "Editor"])
@permission_required("billing.delete_customer", raise_exception=True)
def delete_customer(request, customer_id):
    if request.method == "POST":
        customer = get_object_or_404(Customer, id=customer_id)
        name = customer.full_name
        customer.delete()
        messages.success(request, f"Customer {name} deleted successfully!")
    return redirect("customer_list")
