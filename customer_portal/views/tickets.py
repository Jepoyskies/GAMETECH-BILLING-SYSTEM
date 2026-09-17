from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
import logging

from billing.models import Customer, Notification
from dispatch.models import DispatchRecord, MonitoringRecord, ConfigOption, JobTicket
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


def submit_ticket(request):
    customer_id = request.session.get("customer_id")
    if not customer_id:
        return redirect("customer_portal:portal_login")
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect("customer_portal:portal_login")

    if request.method == "POST":
        issue_type = request.POST.get("issue_type") or "General Concern"
        description = request.POST.get("description") or ""
        alternate_phone = request.POST.get("alternate_phone", "").strip()
        facebook_account = request.POST.get("facebook_account", "").strip()

        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        status_opt = (
            ConfigOption.objects.filter(module="DISPATCH", list_type="STATUS", label__icontains="Pending").first()
            or ConfigOption.objects.filter(module="DISPATCH", list_type="STATUS").first()
        )
        mon_status_opt = (
            ConfigOption.objects.filter(module="MONITORING", list_type="STATUS", label__icontains="Pending").first()
            or ConfigOption.objects.filter(module="MONITORING", list_type="STATUS").first()
        )

        ticket_no = f"TKT-{timezone.now().strftime('%y%m%d%H%M%S')}"
        extra_contacts = []
        if alternate_phone:
            extra_contacts.append(f"Alt Phone: {alternate_phone}")
        if facebook_account:
            extra_contacts.append(f"FB: {facebook_account}")
        extra_contact_str = " | ".join(extra_contacts)

        full_concern = f"[{issue_type}] {description}"
        if extra_contact_str:
            full_concern += f" [On-Site Contact: {extra_contact_str}]"

        dispatch_record = DispatchRecord.objects.create(
            date=timezone.now().date(),
            client_name=customer.full_name,
            address=customer.address or "Not provided",
            contact_number=customer.phone or "Not provided",
            alternate_contact=alternate_phone or None,
            facebook_account=facebook_account or None,
            concern=full_concern,
            source_tab="CLIENT_CONCERNS",
            ticket_number=ticket_no,
            status_option=status_opt,
            customer=customer,
            csr=admin_user,
        )

        MonitoringRecord.objects.create(
            tab_type="CLIENT_CONCERNS",
            date=timezone.now().date(),
            client_name=customer.full_name,
            address=customer.address or "Not provided",
            contact_number=customer.phone or "Not provided",
            alternate_contact=alternate_phone or None,
            facebook_account=facebook_account or None,
            concern=full_concern,
            ticket_number=ticket_no,
            status_option=mon_status_opt,
            dispatch=dispatch_record,
            customer=customer,
            csr=admin_user,
        )

        try:
            barangay_name = customer.barangay.name if customer.barangay else ""
            agent_name = customer.agent.name if customer.agent else ""
            plan_name = customer.plan.name if customer.plan else ""
            lat = float(customer.latitude) if customer.latitude else None
            lng = float(customer.longitude) if customer.longitude else None

            JobTicket.objects.create(
                ticket_number=ticket_no,
                ticket_type="REPAIR",
                status="PENDING",
                priority="NORMAL",
                source_tab="CLIENT_CONCERNS",
                customer=customer,
                mikrotik_device=customer.mikrotik_device,
                client_name=customer.full_name,
                address=customer.address or "",
                barangay=barangay_name,
                contact_number=customer.phone or "",
                alternate_contact=alternate_phone or None,
                facebook_account=facebook_account or None,
                account_no=customer.pppoe_username or "",
                sales_agent=agent_name,
                plan_package=plan_name,
                concern=full_concern,
                chat_type="Customer Portal",
                special_instruction=f"On-Site Contact: {extra_contact_str}" if extra_contact_str else "",
                latitude=lat,
                longitude=lng,
                created_by=admin_user,
            )
        except Exception as e:
            logger.error(f"Error creating JobTicket from portal submit_ticket: {e}")

        try:
            notif_msg = f"[{ticket_no}] {description or issue_type}"
            if extra_contact_str:
                notif_msg += f" ({extra_contact_str})"
            Notification.objects.create(
                title=f"New Ticket: {customer.full_name} ({issue_type})",
                message=notif_msg,
                notification_type="network",
                link="/dispatch/client-concerns/",
            )
        except Exception:
            pass

        messages.success(request, f"Your ticket ({ticket_no}) has been submitted. Our technical dispatch team will review it shortly.")
        return redirect("customer_portal:portal_dashboard")

    recent_tickets = customer.job_tickets.prefetch_related("technicians").order_by("-created_at")[:5]
    return render(request, "customer_portal/submit_ticket.html", {
        "customer": customer,
        "recent_tickets": recent_tickets,
    })


def portal_ticket_history(request):
    """Renders the Ticket & Repair History page for the logged-in portal customer."""
    customer_id = request.session.get("customer_id")
    if not customer_id:
        return redirect("customer_portal:portal_login")
    try:
        customer = Customer.objects.select_related("plan").get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect("customer_portal:portal_login")

    raw_tickets = customer.job_tickets.prefetch_related("technicians", "team").order_by("-created_at")
    raw_dispatches = customer.dispatches.prefetch_related("teams").order_by("-date")

    ticket_history = []
    seen_ticket_nums = set()

    for t in raw_tickets:
        t_num = t.ticket_number or f"TICK-{t.id}"
        seen_ticket_nums.add(t_num)
        ticket_history.append({
            "id": t.id, "ticket_number": t_num, "ticket_type": t.ticket_type,
            "type_display": t.get_ticket_type_display(), "status": t.status,
            "status_display": t.get_status_display(), "created_at": t.created_at,
            "concern": t.concern or "", "alternate_contact": t.alternate_contact or "",
            "facebook_account": t.facebook_account or "",
            "technicians": [tech.name for tech in t.technicians.all()],
            "team_name": t.team.name if t.team else "",
            "actions_taken": t.actions_taken or "", "technician_remarks": t.technician_remarks or "",
            "nap_reading": t.nap_reading or "", "house_reading": t.house_reading or "",
            "signal_level": t.signal_level or "", "ont_modem_sn": t.ont_modem_sn or "",
            "duration": t.duration, "done_at": t.done_at,
        })

    for d in raw_dispatches:
        d_num = d.ticket_number or f"DISP-{d.id}"
        if d_num in seen_ticket_nums:
            continue
        is_repair = (d.source_tab == "CLIENT_CONCERNS")
        created_dt = (
            timezone.datetime.combine(d.date, timezone.datetime.min.time(), tzinfo=timezone.get_current_timezone())
            if d.date else d.created_at
        )
        ticket_history.append({
            "id": d.id, "ticket_number": d_num,
            "ticket_type": "REPAIR" if is_repair else "INSTALLATION",
            "type_display": "Repair / Client Concern" if is_repair else "Installation",
            "status": "COMPLETED" if d.done_at else "PENDING",
            "status_display": "Completed" if d.done_at else "Pending",
            "created_at": created_dt, "concern": d.concern or "",
            "alternate_contact": d.alternate_contact or "", "facebook_account": d.facebook_account or "",
            "technicians": [tech.name for tech in d.teams.all()], "team_name": "",
            "actions_taken": d.actions_taken or "", "technician_remarks": d.remarks or "",
            "nap_reading": "", "house_reading": "", "signal_level": "", "ont_modem_sn": "",
            "duration": d.duration, "done_at": d.done_at,
        })

    ticket_history.sort(key=lambda x: x["created_at"] or timezone.now(), reverse=True)
    open_count = sum(1 for t in ticket_history if t["status"] in ["PENDING", "ASSIGNED", "IN_PROGRESS"])
    completed_count = sum(1 for t in ticket_history if t["status"] == "COMPLETED")

    return render(request, "customer_portal/ticket_history.html", {
        "customer": customer,
        "ticket_history": ticket_history,
        "open_count": open_count,
        "completed_count": completed_count,
        "total_count": len(ticket_history),
        "page_title": "My Support & Repair Tickets",
    })
