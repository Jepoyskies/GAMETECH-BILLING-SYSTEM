from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from billing.models import Customer, SubscriptionPlan
from network_manager.models import MikrotikDevice
from dispatch.models import JobTicket, Team, Technician, JobTicketHistory

@login_required
def dispatch_verification(request):
    """
    Step 1: Staff sees pending Agent prospects, assigns PPPoE, Date/Time,
    verifies the 6 policy guarantees, and generates a Job Order (Ticket).
    """
    if request.method == "POST":
        customer_id = request.POST.get("customer_id")
        pppoe_username = request.POST.get("pppoe_username", "").strip()
        plan_id = request.POST.get("plan_id")
        mikrotik_id = request.POST.get("mikrotik_id")
        scheduled_date = request.POST.get("scheduled_date")
        scheduled_time = request.POST.get("scheduled_time", "").strip()
        
        customer = get_object_or_404(Customer, id=customer_id)
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        mikrotik = get_object_or_404(MikrotikDevice, id=mikrotik_id)
        
        # Validate 6 core customer policy guarantees
        core_checks = [
            ('chk_free_install', 'Free Installation'),
            ('chk_plan_confirmed', 'Plan & Speed Confirmation'),
            ('chk_no_lockin', 'No Lock-in Period'),
            ('chk_staggered', 'Staggered Payments'),
            ('chk_repair_sameday', 'Repair Within the Day'),
            ('chk_rebates_24hr', 'Rebates 24hrs')
        ]
        missing = [label for key, label in core_checks if not request.POST.get(key)]
        if missing:
            messages.error(request, f"Please confirm all 6 policy guarantees before dispatching. Missing: {', '.join(missing)}.")
            return redirect('dispatch_verification')
        
        # Update Customer
        customer.pppoe_username = pppoe_username
        customer.plan = plan
        customer.mikrotik_device = mikrotik
        customer.is_verified = True
        
        payment_method = request.POST.get("preferred_payment_method")
        if payment_method in ['cash', 'gcash']:
            customer.preferred_payment_method = payment_method
        customer.save()
        
        # Create Job Ticket with Agent Handoff Snapshot
        pay_display = customer.get_preferred_payment_method_display()
        ticket_pay_method = (customer.preferred_payment_method or 'CASH').upper()
        if ticket_pay_method not in ['CASH', 'GCASH', 'BANK_TRANSFER', 'OTHER']:
            ticket_pay_method = 'CASH'
        
        ticket = JobTicket.objects.create(
            customer=customer,
            client_name=customer.full_name,
            address=customer.address,
            contact_number=customer.phone,
            account_no=customer.pppoe_username,
            plan_package=plan.name,
            payment_method=ticket_pay_method,
            mikrotik_device=mikrotik,
            sales_agent=customer.agent,
            is_test_data=getattr(customer, 'is_test_data', False),
            scheduled_date=scheduled_date if scheduled_date else None,
            scheduled_time=scheduled_time if scheduled_time else None,
            ticket_type='INSTALLATION',
            status='PENDING',
            source_tab='INTERNET_INSTALL',
            remarks=f"Verified 6 Policy Guarantees. Scheduled: {scheduled_date or 'TBD'} ({scheduled_time or 'Anytime'}). Payment: {pay_display}.",
            special_instruction=f"Payment Preference: {pay_display} | ID: {customer.id_type or 'None'} ({customer.masked_id_number or 'None'})",
            created_by=request.user
        )
        
        # Log History transition
        JobTicketHistory.objects.create(
            job_ticket=ticket,
            actor=request.user,
            from_status="PROSPECT",
            to_status="PENDING",
            note=f"Stage 1 Verification completed by {request.user.get_full_name() or request.user.username}. Confirmed: Free Install, Plan {plan.name}, No Lock-in, Staggered Payments, Same-day Repair, 24hr Rebates. Scheduled: {scheduled_date or 'TBD'} ({scheduled_time or 'Anytime'}). PPPoE: {pppoe_username}. Payment: {pay_display}."
        )
        
        messages.success(request, f"Verified prospect {customer.full_name} and generated Job Ticket {ticket.ticket_number}.")
        return redirect('dispatch_assignment')
        
    # Trigger SLA check on pipeline load
    try:
        from billing.tasks import check_dispatch_sla_breaches_task
        check_dispatch_sla_breaches_task()
    except Exception:
        pass

    from billing.models import Barangay
    prospects = Customer.objects.filter(status='pending', is_verified=False)
    plans = SubscriptionPlan.objects.all()
    mikrotiks = MikrotikDevice.objects.all()
    barangays = Barangay.objects.all()
    today = timezone.now().date().strftime("%Y-%m-%d")
    
    return render(request, "dispatch/pipeline/1_verification.html", {
        "prospects": prospects,
        "plans": plans,
        "mikrotiks": mikrotiks,
        "barangays": barangays,
        "today": today
    })

@login_required
def dispatch_assignment(request):
    """
    Step 2: Assign Tech/Team to the generated Job Ticket.
    """
    if request.method == "POST":
        ticket_id = request.POST.get("ticket_id")
        team_id = request.POST.get("team_id")
        scheduled_date = request.POST.get("scheduled_date")
        scheduled_time = request.POST.get("scheduled_time")
        tech_ids = request.POST.getlist("tech_ids")
        
        ticket = get_object_or_404(JobTicket, id=ticket_id)
        team = get_object_or_404(Team, id=team_id) if team_id else None
        
        ticket.team = team
        ticket.scheduled_date = scheduled_date
        ticket.scheduled_time = scheduled_time
        ticket.status = 'ASSIGNED'
        ticket.save()
        
        if tech_ids:
            ticket.technicians.set(tech_ids)
            
        messages.success(request, f"Assigned {ticket.ticket_number} to team.")
        return redirect('dispatch_assignment')

    # Trigger SLA check on pipeline load
    try:
        from billing.tasks import check_dispatch_sla_breaches_task
        check_dispatch_sla_breaches_task()
    except Exception:
        pass

    pending_tickets = JobTicket.objects.filter(status='PENDING').select_related('customer', 'team').prefetch_related('technicians').order_by('-created_at')
    ongoing_tickets = JobTicket.objects.filter(status__in=['ASSIGNED', 'IN_PROGRESS']).select_related('customer', 'team').prefetch_related('technicians').order_by('-contact_attempt_count', '-created_at')
    teams = Team.objects.all()
    technicians = Technician.objects.all()
    active_tab = request.GET.get('tab', 'pending')
    
    return render(request, "dispatch/pipeline/2_assignment.html", {
        "pending_tickets": pending_tickets,
        "ongoing_tickets": ongoing_tickets,
        "teams": teams,
        "technicians": technicians,
        "active_tab": active_tab,
        "pending_count": pending_tickets.count(),
        "ongoing_count": ongoing_tickets.count(),
    })

@login_required
def dispatch_undispatch(request, ticket_id):
    """
    Undispatch: Bounces an Assigned or In-Progress JobTicket back to Pending.
    Clears the assigned team and technicians, resets timers, and logs an audit history entry.
    """
    if request.method == "POST":
        ticket = get_object_or_404(JobTicket, id=ticket_id)
        if ticket.status in ['ASSIGNED', 'IN_PROGRESS']:
            old_status = ticket.status
            old_team_name = ticket.team.name if ticket.team else 'No Team'
            ticket.status = 'PENDING'
            ticket.team = None
            ticket.technicians.clear()
            ticket.time_start = None
            ticket.save()

            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status=old_status,
                to_status="PENDING",
                note=f"Undispatched by {request.user.get_full_name() or request.user.username}. Removed from {old_team_name} and returned to Pending assignment queue."
            )
            messages.success(request, f"Ticket {ticket.ticket_number} successfully undispatched and returned to Pending queue.")
        else:
            messages.warning(request, f"Ticket {ticket.ticket_number} is in {ticket.status} status and cannot be undispatched.")
    return redirect('dispatch_assignment')

@login_required
def technician_mobile_ui(request):
    """
    Step 3: Mobile UI for Technicians to see jobs, start timer, 
    and fill physical form specs.
    """
    try:
        tech = request.user.technician
    except:
        messages.error(request, "You are not registered as a Technician.")
        return redirect("dashboard")
        
    assigned_tickets = tech.job_tickets.filter(status__in=['ASSIGNED', 'IN_PROGRESS'])
    
    if request.method == "POST":
        action = request.POST.get("action")
        ticket_id = request.POST.get("ticket_id")
        ticket = get_object_or_404(JobTicket, id=ticket_id)
        
        if action == "START":
            ticket.time_start = timezone.now()
            ticket.status = 'IN_PROGRESS'
            ticket.save()
            messages.success(request, "Installation timer started.")
            
        elif action == "DONE":
            ticket.time_accomplish = timezone.now()
            # Calculate duration in minutes
            if ticket.time_start:
                diff = ticket.time_accomplish - ticket.time_start
                ticket.duration = int(diff.total_seconds() / 60)
            
            # Fill form fields
            ticket.nap_port = request.POST.get("nap_port")
            ticket.cable_length = request.POST.get("cable_length")
            ticket.nap_reading = request.POST.get("nap_reading")
            ticket.pole_number = request.POST.get("pole_number")
            ticket.ont_modem_sn = request.POST.get("ont_modem_sn") or request.POST.get("onu_sn_mac")
            ticket.signal_level = request.POST.get("signal_level") or request.POST.get("signal_dbm")
            ticket.facility = request.POST.get("facility")
            ticket.house_reading = request.POST.get("house_reading")
            ticket.technician_remarks = request.POST.get("technician_remarks")
            ticket.acknowledged_by = request.POST.get("acknowledged_by")
            ticket.payment_collected = request.POST.get("payment_method")
            ticket.done_at = timezone.now()
            if ticket.duration:
                ticket.done_duration = ticket.duration
            
            ticket.status = 'COMPLETED'  # Wait for QA
            ticket.save()
            messages.success(request, "Job marked as Done. Submitted for QA.")
            
        return redirect('technician_mobile_ui')
        
    active_ticket = assigned_tickets.first()
    return render(request, "dispatch/pipeline/3_tech_mobile.html", {
        "tickets": assigned_tickets,
        "ticket": active_ticket
    })

@login_required
def dispatch_qa(request):
    """
    Step 4: QA Check (Staff) - reviews technician's form, 
    confirms customer satisfaction, passes to Admin.
    """
    if request.method == "POST":
        ticket_id = request.POST.get("ticket_id")
        ticket = get_object_or_404(JobTicket, id=ticket_id)
        
        action = request.POST.get("action")
        qa_notes = request.POST.get("qa_notes")
        
        if action == 'approve':
            ticket.qa_notes = qa_notes
            ticket.qa_completed_at = timezone.now()
            ticket.status = 'QA_PASSED'
            ticket.save()
            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status='COMPLETED',
                to_status='QA_PASSED',
                note=f"QA Check Passed: {qa_notes or 'Customer satisfied and specs verified.'}"
            )
            messages.success(request, f"Ticket {ticket.ticket_number} passed QA and sent to Admin.")
        elif action == 'bounce_back':
            timestamp_str = timezone.now().strftime("%b %d, %I:%M %p")
            ticket.remarks = f"[{timestamp_str}] QA BOUNCED TO TECH by {request.user.username}: {qa_notes}\n" + (ticket.remarks or "")
            ticket.status = 'IN_PROGRESS'  # Send back to Tech
            ticket.save()
            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status='COMPLETED',
                to_status='IN_PROGRESS',
                note=f"QA Bounced back to Technician: {qa_notes}"
            )
            messages.warning(request, f"Bounced ticket {ticket.ticket_number} back to Technician.")
            
        return redirect('dispatch_qa')

    qa_tickets = JobTicket.objects.filter(status='COMPLETED', customer__status='pending')
    
    return render(request, "dispatch/pipeline/4_qa.html", {
        "tickets": qa_tickets
    })

@login_required
def dispatch_approval(request):
    """
    Step 5: Admin Final Approval - Activates Customer.
    """
    if request.method == "POST":
        ticket_id = request.POST.get("ticket_id")
        ticket = get_object_or_404(JobTicket, id=ticket_id)
        
        action = request.POST.get("action")
        
        if action == 'approve':
            customer = ticket.customer
            if customer:
                customer.status = 'active'
                customer.installation_status = 'installed'
                customer.installed_at = timezone.now()
                # 60-day lock on staggered payments if referred by an agent
                if customer.agent:
                    customer.agent_lock_until = timezone.now() + timezone.timedelta(days=60)
                customer.save()
            ticket.status = 'COMPLETED_AND_VERIFIED'
            ticket.done_at = timezone.now()
            ticket.save()
            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status='QA_PASSED',
                to_status='COMPLETED_AND_VERIFIED',
                note="Super Admin Final Sign-Off & Activation Approved."
            )
            messages.success(request, f"Customer {customer.full_name} is now ACTIVE.")
        elif action == 'bounce_dispatch':
            admin_notes = request.POST.get("admin_notes", "No notes provided.")
            timestamp_str = timezone.now().strftime("%b %d, %I:%M %p")
            ticket.remarks = f"[{timestamp_str}] ADMIN BOUNCED TO QA by {request.user.username}: {admin_notes}\n" + (ticket.remarks or "")
            ticket.status = 'COMPLETED'  # Sends back to QA
            ticket.save()
            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status='QA_PASSED',
                to_status='COMPLETED',
                note=f"Admin Bounced back to Dispatch QA: {admin_notes}"
            )
            messages.warning(request, f"Bounced ticket {ticket.ticket_number} back to Dispatch QA.")
        elif action == 'bounce_tech':
            admin_notes = request.POST.get("admin_notes", "No notes provided.")
            timestamp_str = timezone.now().strftime("%b %d, %I:%M %p")
            ticket.remarks = f"[{timestamp_str}] ADMIN BOUNCED TO TECH by {request.user.username}: {admin_notes}\n" + (ticket.remarks or "")
            ticket.status = 'IN_PROGRESS'  # Sends back to Tech
            ticket.save()
            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status='QA_PASSED',
                to_status='IN_PROGRESS',
                note=f"Admin Bounced back to Technician: {admin_notes}"
            )
            messages.error(request, f"Bounced ticket {ticket.ticket_number} all the way back to Technician.")
            
        return redirect('dispatch_approval')
        
    approval_tickets = JobTicket.objects.filter(status='QA_PASSED')
    
    return render(request, "dispatch/pipeline/5_approval.html", {
        "tickets": approval_tickets
    })
