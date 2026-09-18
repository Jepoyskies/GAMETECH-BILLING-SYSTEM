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

        email = (request.POST.get("email") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        pppoe_username = (request.POST.get("pppoe_username") or "").strip()

        # Duplicate checks
        if phone and Customer.objects.filter(phone=phone).exists():
            messages.error(request, "A customer with this phone number already exists.")
            context = {
                "categorized_plans": get_categorized_plans(),
                "devices": MikrotikDevice.objects.all(),
                "agents": Agent.objects.all(),
                "barangays": Barangay.objects.all(),
                "account_types": AccountType.objects.all(),
                "prefill_username": pppoe_username,
            }
            return render(request, "billing/add_customer.html", context)

        if email and Customer.objects.filter(email__iexact=email).exists():
            messages.error(request, "A customer with this email address already exists.")
            context = {
                "categorized_plans": get_categorized_plans(),
                "devices": MikrotikDevice.objects.all(),
                "agents": Agent.objects.all(),
                "barangays": Barangay.objects.all(),
                "account_types": AccountType.objects.all(),
                "prefill_username": pppoe_username,
            }
            return render(request, "billing/add_customer.html", context)

        if pppoe_username and Customer.objects.filter(pppoe_username__iexact=pppoe_username).exists():
            messages.error(request, "A customer with this PPPoE username already exists.")
            context = {
                "categorized_plans": get_categorized_plans(),
                "devices": MikrotikDevice.objects.all(),
                "agents": Agent.objects.all(),
                "barangays": Barangay.objects.all(),
                "account_types": AccountType.objects.all(),
                "prefill_username": pppoe_username,
            }
            return render(request, "billing/add_customer.html", context)

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

        installation_status = request.POST.get("installation_status")
        if not installation_status:
            installation_status = "pending"

        installed_at_val = None
        installed_at_str = request.POST.get("installed_at")
        if installed_at_str:
            try:
                installed_at_val = timezone.datetime.strptime(installed_at_str, "%Y-%m-%d")
                if timezone.is_naive(installed_at_val):
                    installed_at_val = timezone.make_aware(installed_at_val)
            except ValueError:
                installed_at_val = timezone.now()
        elif installation_status == "installed":
            installed_at_val = timezone.now()

        expires_at_val = None
        expires_at_str = request.POST.get("expires_at")
        if expires_at_str:
            try:
                expires_at_val = timezone.datetime.strptime(expires_at_str, "%Y-%m-%d")
            except ValueError:
                expires_at_val = None

        if installation_status == "pending":
            cust_status = "pending"
        else:
            cust_status = "pending" if request.user.role == "Agent" else request.POST.get("status", "active")

        customer = Customer.objects.create(
            full_name=request.POST.get("full_name"),
            email=request.POST.get("email") or None,
            phone=request.POST.get("phone"),
            address=request.POST.get("address"),
            pppoe_username=request.POST.get("pppoe_username") or None,
            pppoe_password=request.POST.get("pppoe_password") or get_random_string(8),
            status=cust_status,
            installation_status=installation_status,
            installed_at=installed_at_val,
            expires_at=expires_at_val,
            plan_id=request.POST.get("plan_id"),
            mikrotik_device_id=request.POST.get("device_id") or None,
            agent_id=request.POST.get("agent_id") or None,
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
            new_data=f"Name: {customer.full_name}\nPhone: {customer.phone}\nStatus: {customer.status}\nInstallation: {customer.installation_status}",
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
        email = (request.POST.get("email") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        pppoe_username = (request.POST.get("pppoe_username") or "").strip()

        # Duplicate checks (excluding self)
        if phone and Customer.objects.filter(phone=phone).exclude(pk=customer.pk).exists():
            messages.error(request, "A customer with this phone number already exists.")
            context = {
                "customer": customer,
                "categorized_plans": get_categorized_plans(),
                "devices": MikrotikDevice.objects.all(),
                "agents": Agent.objects.all(),
                "barangays": Barangay.objects.all(),
                "account_types": AccountType.objects.all(),
            }
            return render(request, "billing/edit_customer.html", context)

        if email and Customer.objects.filter(email__iexact=email).exclude(pk=customer.pk).exists():
            messages.error(request, "A customer with this email address already exists.")
            context = {
                "customer": customer,
                "categorized_plans": get_categorized_plans(),
                "devices": MikrotikDevice.objects.all(),
                "agents": Agent.objects.all(),
                "barangays": Barangay.objects.all(),
                "account_types": AccountType.objects.all(),
            }
            return render(request, "billing/edit_customer.html", context)

        if pppoe_username and Customer.objects.filter(pppoe_username__iexact=pppoe_username).exclude(pk=customer.pk).exists():
            messages.error(request, "A customer with this PPPoE username already exists.")
            context = {
                "customer": customer,
                "categorized_plans": get_categorized_plans(),
                "devices": MikrotikDevice.objects.all(),
                "agents": Agent.objects.all(),
                "barangays": Barangay.objects.all(),
                "account_types": AccountType.objects.all(),
            }
            return render(request, "billing/edit_customer.html", context)

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

        new_install_status = request.POST.get("installation_status")
        if new_install_status:
            check_change("Installation Status", customer.installation_status, new_install_status)
            customer.installation_status = new_install_status

        new_installed_at_str = request.POST.get("installed_at")
        if new_installed_at_str:
            try:
                new_installed_at = timezone.datetime.strptime(new_installed_at_str, "%Y-%m-%d")
                if timezone.is_naive(new_installed_at):
                    new_installed_at = timezone.make_aware(new_installed_at)
                curr_installed_str = customer.installed_at.strftime("%Y-%m-%d") if customer.installed_at else ""
                if curr_installed_str != new_installed_at_str:
                    check_change("Installation Date", curr_installed_str or "None", new_installed_at_str)
                    customer.installed_at = new_installed_at
            except ValueError:
                pass

        new_expires_at_str = request.POST.get("expires_at")
        if new_expires_at_str is not None and new_status != "suspended":
            curr_expires_str = customer.expires_at.strftime("%Y-%m-%d") if customer.expires_at else ""
            if new_expires_at_str and curr_expires_str != new_expires_at_str:
                try:
                    new_expires_dt = timezone.datetime.strptime(new_expires_at_str, "%Y-%m-%d")
                    check_change("Expiration Date", curr_expires_str or "None", new_expires_at_str)
                    customer.expires_at = new_expires_dt
                except ValueError:
                    pass
            elif not new_expires_at_str and curr_expires_str:
                check_change("Expiration Date", curr_expires_str, "None")
                customer.expires_at = None

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

    # 5. Tickets & Repairs History (JobTicket & legacy DispatchRecord)
    from dispatch.models import JobTicket, DispatchRecord
    raw_tickets = customer.job_tickets.prefetch_related('technicians', 'team').order_by('-created_at')
    raw_dispatches = customer.dispatches.prefetch_related('teams').order_by('-date')

    ticket_history = []
    seen_ticket_nums = set()

    for t in raw_tickets:
        t_num = t.ticket_number or f"TICK-{t.id}"
        seen_ticket_nums.add(t_num)
        tech_list = [tech.name for tech in t.technicians.all()]
        is_repair = (t.ticket_type == 'REPAIR' or t.source_tab == 'CLIENT_CONCERNS')
        ticket_history.append({
            "id": t.id,
            "ticket_number": t_num,
            "ticket_type": t.ticket_type,
            "type_display": t.get_ticket_type_display(),
            "status": t.status,
            "status_display": t.get_status_display(),
            "created_at": t.created_at,
            "concern": t.concern or '',
            "alternate_contact": t.alternate_contact or '',
            "facebook_account": t.facebook_account or '',
            "technicians": tech_list,
            "team_name": t.team.name if t.team else '',
            "actions_taken": t.actions_taken or '',
            "technician_remarks": t.technician_remarks or '',
            "nap_reading": t.nap_reading or '',
            "house_reading": t.house_reading or '',
            "signal_level": t.signal_level or '',
            "ont_modem_sn": t.ont_modem_sn or '',
            "duration": t.duration,
            "done_at": t.done_at,
            "is_repair": is_repair,
            "is_modern": True,
        })

    for d in raw_dispatches:
        d_num = d.ticket_number or f"DISP-{d.id}"
        if d_num in seen_ticket_nums:
            continue
        tech_list = [tech.name for tech in d.teams.all()]
        is_repair = (d.source_tab == 'CLIENT_CONCERNS')
        created_dt = timezone.datetime.combine(d.date, timezone.datetime.min.time(), tzinfo=timezone.get_current_timezone()) if d.date else d.created_at
        ticket_history.append({
            "id": d.id,
            "ticket_number": d_num,
            "ticket_type": 'REPAIR' if is_repair else 'INSTALLATION',
            "type_display": 'Repair / Client Concern' if is_repair else 'Installation',
            "status": 'COMPLETED' if d.done_at else 'PENDING',
            "status_display": 'Completed' if d.done_at else 'Pending',
            "created_at": created_dt,
            "concern": d.concern or '',
            "alternate_contact": d.alternate_contact or '',
            "facebook_account": d.facebook_account or '',
            "technicians": tech_list,
            "team_name": '',
            "actions_taken": d.actions_taken or '',
            "technician_remarks": d.remarks or '',
            "nap_reading": '',
            "house_reading": '',
            "signal_level": '',
            "ont_modem_sn": '',
            "duration": d.duration,
            "done_at": d.done_at,
            "is_repair": is_repair,
            "is_modern": False,
        })

    # Sort ticket history by created_at descending
    ticket_history.sort(key=lambda x: x["created_at"] or timezone.now(), reverse=True)

    # Calculate Repair Quality & Repeat Repair Audit Metrics
    repair_items = [t for t in ticket_history if t["is_repair"]]
    repair_count = len(repair_items)

    repeat_repair_alerts = []
    chronological_repairs = sorted(repair_items, key=lambda x: x["created_at"] or timezone.now())
    for i in range(1, len(chronological_repairs)):
        prev_rep = chronological_repairs[i - 1]
        curr_rep = chronological_repairs[i]
        if prev_rep["created_at"] and curr_rep["created_at"]:
            gap_days = (curr_rep["created_at"].date() - prev_rep["created_at"].date()).days
            if gap_days <= 30:
                prev_techs = ", ".join(prev_rep["technicians"]) or "Unassigned"
                curr_techs = ", ".join(curr_rep["technicians"]) or "Unassigned"
                repeat_repair_alerts.append({
                    "prev_ticket": prev_rep["ticket_number"],
                    "curr_ticket": curr_rep["ticket_number"],
                    "gap_days": gap_days,
                    "prev_date": prev_rep["created_at"],
                    "curr_date": curr_rep["created_at"],
                    "prev_techs": prev_techs,
                    "curr_techs": curr_techs,
                    "prev_concern": prev_rep["concern"],
                    "curr_concern": curr_rep["concern"],
                    "prev_actions": prev_rep["actions_taken"],
                })

    has_repeat_repairs = len(repeat_repair_alerts) > 0 or repair_count >= 2

    # Include tickets into all_logs
    for t in ticket_history:
        tech_str = ", ".join(t["technicians"]) or t["team_name"] or "Tech Dispatch"
        all_logs.append({
            "type": "ticket",
            "date": t["created_at"],
            "title": f"Ticket: {t['ticket_number']}",
            "details": f"{t['type_display']} — Status: {t['status_display']} | Concern: {t['concern'] or 'None'} | Tech: {tech_str}",
            "user": tech_str,
            "log_obj": None,
        })

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

    jobs_done_count = sum(1 for t in ticket_history if t.get("status") in ['COMPLETED', 'QA_PASSED'])
    jobs_pending_count = sum(1 for t in ticket_history if t.get("status") not in ['COMPLETED', 'QA_PASSED', 'CANCELLED'])
    install_jobs_count = sum(1 for t in ticket_history if t.get("ticket_type") == 'INSTALLATION')
    repair_jobs_count = len(repair_items)
    cignal_jobs_count = sum(1 for t in ticket_history if t.get("ticket_type") == 'CIGNAL')
    migration_jobs_count = sum(1 for t in ticket_history if t.get("ticket_type") == 'MIGRATION')

    context = {
        "customer": customer,
        "plans": SubscriptionPlan.objects.all().order_by("price"),
        "payments": payments,
        "all_logs": all_logs,
        "ticket_history": ticket_history,
        "repair_count": repair_count,
        "total_tickets_count": len(ticket_history),
        "jobs_done_count": jobs_done_count,
        "jobs_pending_count": jobs_pending_count,
        "install_jobs_count": install_jobs_count,
        "repair_jobs_count": repair_jobs_count,
        "cignal_jobs_count": cignal_jobs_count,
        "migration_jobs_count": migration_jobs_count,
        "repeat_repair_alerts": repeat_repair_alerts,
        "has_repeat_repairs": has_repeat_repairs,
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
