import csv
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Max
from billing.models import Customer
from network_manager.models import MikrotikDevice
from .models import (
    JobTicket, JobTicketHistory, DispatchRecord, MonitoringRecord, JobDetail,
    ConfigOption, Technician, Team, AuditLog
)
from .forms import MonitoringRecordForm, DispatchRecordForm, JobDetailForm
from .reports import get_csr_performance_report, get_technician_productivity_report
from .analytics import (
    get_operational_overview_stats, get_overview_kpis_and_chart,
    get_monitoring_summary, get_monthly_targets_data
)

logger = logging.getLogger(__name__)


def log_audit(action, entity_type, entity_id, actor, summary=None, before=None, after=None):
    try:
        AuditLog.objects.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor if (actor and actor.is_authenticated) else None,
            summary=summary,
            before_data=before,
            after_data=after
        )
    except Exception as e:
        logger.warning(f"Failed to record dispatch audit log: {e}")


@login_required
def dispatch_index_view(request):
    if hasattr(request.user, "agent_profile") and not request.user.is_staff:
        return redirect('agent_dashboard')
    return redirect('dispatch_dashboard')


@login_required
def dashboard_view(request):
    if hasattr(request.user, "agent_profile") and not request.user.is_staff:
        return redirect('agent_dashboard')
    today = timezone.now().date()
    
    # Pipeline KPI statistics
    pending_verification_count = Customer.objects.filter(status='pending', is_verified=False).count()
    awaiting_assignment_count = JobTicket.objects.filter(status='PENDING').count()
    active_in_field_count = JobTicket.objects.filter(status__in=['ASSIGNED', 'IN_PROGRESS']).count()
    pending_qa_approval_count = JobTicket.objects.filter(status__in=['COMPLETED', 'QA_PASSED']).count()
    
    total_techs_count = Technician.objects.count()
    
    # Filter parameters
    status_filter = request.GET.get('status', 'ALL')
    type_filter = request.GET.get('type', 'ALL')
    source_tab_filter = request.GET.get('source_tab', 'ALL')
    team_filter = request.GET.get('team', 'ALL')
    search_q = request.GET.get('q', '').strip()
    date_filter = request.GET.get('date_range', 'all')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    
    # Operational Rule: Live Queue Cards ALWAYS ignore the date filter (showing current live reality)
    pending_verification_count = Customer.objects.filter(status='pending', is_verified=False).count()
    awaiting_assignment_count = JobTicket.objects.filter(status='PENDING').count()
    active_in_field_count = JobTicket.objects.filter(status__in=['ASSIGNED', 'IN_PROGRESS']).count()
    pending_qa_approval_count = JobTicket.objects.filter(status__in=['COMPLETED', 'QA_PASSED']).count()
    total_techs_count = Technician.objects.count()

    # Closed and historical metrics: respect the date filter (completion date)
    closed_qs = JobTicket.objects.filter(status__in=['COMPLETED', 'QA_PASSED'])
    cancelled_qs = JobTicket.objects.filter(status='CANCELLED')
    
    tickets_qs = JobTicket.objects.select_related('customer', 'team', 'mikrotik_device').prefetch_related('technicians')
    
    if date_filter == 'today':
        tickets_qs = tickets_qs.filter(created_at__date=today)
        closed_qs = closed_qs.filter(done_at__date=today)
        cancelled_qs = cancelled_qs.filter(updated_at__date=today)
    elif date_filter == 'this_month':
        tickets_qs = tickets_qs.filter(created_at__year=today.year, created_at__month=today.month)
        closed_qs = closed_qs.filter(done_at__year=today.year, done_at__month=today.month)
        cancelled_qs = cancelled_qs.filter(updated_at__year=today.year, updated_at__month=today.month)
    elif date_filter == 'custom' and date_from and date_to:
        tickets_qs = tickets_qs.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
        closed_qs = closed_qs.filter(done_at__date__gte=date_from, done_at__date__lte=date_to)
        cancelled_qs = cancelled_qs.filter(updated_at__date__gte=date_from, updated_at__date__lte=date_to)

    closed_count = closed_qs.count()
    cancelled_count = cancelled_qs.count()
    
    if status_filter != 'ALL':
        tickets_qs = tickets_qs.filter(status=status_filter)
    if type_filter != 'ALL':
        tickets_qs = tickets_qs.filter(ticket_type=type_filter)
    if source_tab_filter != 'ALL':
        if source_tab_filter == 'CLIENT_CONCERNS':
            tickets_qs = tickets_qs.filter(Q(source_tab='CLIENT_CONCERNS') | Q(chat_type__icontains='concern'))
        else:
            tickets_qs = tickets_qs.filter(source_tab=source_tab_filter)
    if team_filter != 'ALL' and team_filter.isdigit():
        tickets_qs = tickets_qs.filter(team_id=int(team_filter))
    if search_q:
        tickets_qs = tickets_qs.filter(
            Q(ticket_number__icontains=search_q) |
            Q(client_name__icontains=search_q) |
            Q(contact_number__icontains=search_q) |
            Q(address__icontains=search_q) |
            Q(barangay__icontains=search_q) |
            Q(account_no__icontains=search_q)
        )
        
    tickets = tickets_qs.order_by('-created_at')[:100]
    teams = Team.objects.prefetch_related('members').all()
    technicians = Technician.objects.select_related('team').all()
    mikrotik_devices = MikrotikDevice.objects.all()
    
    # Map points payload
    map_points = []
    for t in tickets_qs.filter(latitude__isnull=False, longitude__isnull=False)[:200]:
        map_points.append({
            'id': t.id,
            'ticket_number': t.ticket_number,
            'client_name': t.client_name,
            'address': t.address or '',
            'barangay': t.barangay or '',
            'contact_number': t.contact_number or '',
            'alternate_contact': t.alternate_contact or '',
            'facebook_account': t.facebook_account or '',
            'ticket_type': t.get_ticket_type_display(),
            'status': t.status,
            'priority': t.priority,
            'lat': t.latitude,
            'lng': t.longitude,
            'plan_package': t.plan_package or '',
            'payment_method': t.payment_method or 'CASH',
            'concern': t.concern or '',
            'assigned_team': t.team.name if t.team else 'Unassigned',
            'scheduled_date': t.scheduled_date.strftime('%b %d, %Y') if t.scheduled_date else 'Not scheduled',
        })
        
    # Compute Legacy Analytical Sections
    operational_overview = get_operational_overview_stats()
    overview_data = get_overview_kpis_and_chart(date_filter=date_filter, date_from=date_from, date_to=date_to)
    monitoring_summary = get_monitoring_summary(date_filter=date_filter, date_from=date_from, date_to=date_to)
    monthly_targets = get_monthly_targets_data()
    csr_report = get_csr_performance_report(date_filter=date_filter, date_from=date_from, date_to=date_to)
    tech_report = get_technician_productivity_report(date_filter=date_filter, date_from=date_from, date_to=date_to)

    context = {
        'pending_verification_count': pending_verification_count,
        'awaiting_assignment_count': awaiting_assignment_count,
        'active_in_field_count': active_in_field_count,
        'pending_qa_approval_count': pending_qa_approval_count,
        'total_techs_count': total_techs_count,
        'closed_count': closed_count,
        'cancelled_count': cancelled_count,
        'tickets': tickets,
        'teams': teams,
        'technicians': technicians,
        'mikrotik_devices': mikrotik_devices,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'source_tab_filter': source_tab_filter,
        'team_filter': team_filter,
        'search_q': search_q,
        'date_filter': date_filter,
        'date_from': date_from,
        'date_to': date_to,
        'map_points_json': json.dumps(map_points),
        'operational_overview': operational_overview,
        'overview_data': overview_data,
        'monitoring_summary': monitoring_summary,
        'monthly_targets': monthly_targets,
        'csr_report': csr_report,
        'tech_report': tech_report,
    }
    return render(request, 'dispatch/dashboard.html', context)


# ─────────────────────────────────────────────
# JSON REST APIs FOR FAST INTERACTIVE UI
# ─────────────────────────────────────────────

@login_required
def api_tickets_list(request):
    status_filter = request.GET.get('status', 'ALL')
    type_filter = request.GET.get('type', 'ALL')
    search_q = request.GET.get('q', '').strip()
    
    qs = JobTicket.objects.select_related('customer', 'team').prefetch_related('technicians')
    if status_filter != 'ALL':
        qs = qs.filter(status=status_filter)
    if type_filter != 'ALL':
        qs = qs.filter(ticket_type=type_filter)
    if search_q:
        qs = qs.filter(
            Q(ticket_number__icontains=search_q) |
            Q(client_name__icontains=search_q) |
            Q(contact_number__icontains=search_q) |
            Q(address__icontains=search_q) |
            Q(barangay__icontains=search_q) |
            Q(account_no__icontains=search_q)
        )
        
    data = []
    for t in qs[:150]:
        data.append({
            'id': t.id,
            'ticket_number': t.ticket_number,
            'client_name': t.client_name,
            'address': t.address,
            'barangay': t.barangay,
            'contact_number': t.contact_number,
            'alternate_contact': t.alternate_contact,
            'facebook_account': t.facebook_account,
            'account_no': t.account_no,
            'ticket_type': t.ticket_type,
            'ticket_type_display': t.get_ticket_type_display(),
            'status': t.status,
            'status_display': t.get_status_display(),
            'priority': t.priority,
            'priority_display': t.get_priority_display(),
            'plan_package': t.plan_package,
            'concern': t.concern,
            'team_id': t.team_id,
            'team_name': t.team.name if t.team else None,
            'technicians': [tech.name for tech in t.technicians.all()],
            'scheduled_date': t.scheduled_date.isoformat() if t.scheduled_date else None,
            'scheduled_time': t.scheduled_time,
            'latitude': t.latitude,
            'longitude': t.longitude,
            'created_at': t.created_at.strftime('%b %d, %Y %I:%M %p'),
        })
    return JsonResponse({'success': True, 'count': len(data), 'tickets': data})


@login_required
def api_ticket_detail(request, ticket_id):
    ticket = get_object_or_404(JobTicket.objects.select_related('customer', 'team', 'mikrotik_device'), id=ticket_id)
    return JsonResponse({
        'success': True,
        'ticket': {
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'client_name': ticket.client_name,
            'address': ticket.address,
            'barangay': ticket.barangay,
            'contact_number': ticket.contact_number,
            'alternate_contact': ticket.alternate_contact,
            'facebook_account': ticket.facebook_account,
            'account_no': ticket.account_no,
            'sales_agent': ticket.sales_agent,
            'plan_package': ticket.plan_package,
            'concern': ticket.concern,
            'remarks': ticket.remarks,
            'special_instruction': ticket.special_instruction,
            'actions_taken': ticket.actions_taken,
            'ticket_type': ticket.ticket_type,
            'ticket_type_display': ticket.get_ticket_type_display(),
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
            'priority': ticket.priority,
            'team_id': ticket.team_id,
            'team_name': ticket.team.name if ticket.team else None,
            'technician_ids': list(ticket.technicians.values_list('id', flat=True)),
            'technicians': [tech.name for tech in ticket.technicians.all()],
            'scheduled_date': ticket.scheduled_date.isoformat() if ticket.scheduled_date else None,
            'scheduled_time': ticket.scheduled_time,
            'latitude': ticket.latitude,
            'longitude': ticket.longitude,
            # Technical Specs
            'nap_port': ticket.nap_port,
            'cable_length': ticket.cable_length,
            'nap_reading': ticket.nap_reading,
            'pole_number': ticket.pole_number,
            'ont_modem_sn': ticket.ont_modem_sn,
            'signal_level': ticket.signal_level,
            'facility': ticket.facility,
            'house_reading': ticket.house_reading,
            'technician_remarks': ticket.technician_remarks,
            'acknowledged_by': ticket.acknowledged_by,
            # Customer & Mikrotik Links
            'customer_id': ticket.customer_id,
            'customer_name': ticket.customer.full_name if ticket.customer else None,
            'mikrotik_device_id': ticket.mikrotik_device_id,
            'mikrotik_name': ticket.mikrotik_device.device_name if ticket.mikrotik_device else None,
            'created_at': ticket.created_at.strftime('%b %d, %Y %I:%M %p'),
            'updated_at': ticket.updated_at.strftime('%b %d, %Y %I:%M %p'),
        }
    })


@login_required
def api_create_ticket(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        client_name = data.get('client_name', '').strip()
        if not client_name:
            return JsonResponse({'success': False, 'error': 'Client name is required.'}, status=400)
            
        agent_obj = None
        sales_agent_val = data.get('sales_agent')
        if sales_agent_val:
            from billing.models import Agent
            val_clean = str(sales_agent_val).strip()
            if val_clean.lower() not in ['', 'none', 'null', 'walk-in', 'direct', 'walk-in / direct', 'walk-in/direct', 'walkin']:
                if val_clean.isdigit():
                    agent_obj = Agent.objects.filter(id=int(val_clean)).first()
                if not agent_obj:
                    agent_obj = Agent.objects.filter(name__iexact=val_clean).first()
        
        cust_id = data.get('customer_id') or None
        is_test = False
        if cust_id:
            from billing.models import Customer
            cust = Customer.objects.filter(id=cust_id).first()
            if cust:
                if not agent_obj and cust.agent:
                    agent_obj = cust.agent
                if getattr(cust, 'is_test_data', False):
                    is_test = True
        if agent_obj and getattr(agent_obj, 'is_test_data', False):
            is_test = True

        raw_pay_method = data.get('payment_method', 'CASH').upper()
        if raw_pay_method not in ['CASH', 'GCASH', 'BANK_TRANSFER', 'OTHER']:
            raw_pay_method = 'CASH'

        ticket = JobTicket.objects.create(
            client_name=client_name,
            address=data.get('address', '').strip(),
            barangay=data.get('barangay', '').strip(),
            contact_number=data.get('contact_number', '').strip(),
            account_no=data.get('account_no', '').strip(),
            sales_agent=agent_obj,
            is_test_data=is_test,
            plan_package=data.get('plan_package', '').strip(),
            payment_method=raw_pay_method,
            ticket_type=data.get('ticket_type', 'INSTALLATION'),
            priority=data.get('priority', 'NORMAL'),
            status='PENDING',
            concern=data.get('concern', '').strip(),
            remarks=data.get('remarks', '').strip(),
            special_instruction=data.get('special_instruction', '').strip(),
            created_by=request.user,
            latitude=float(data.get('latitude')) if data.get('latitude') else None,
            longitude=float(data.get('longitude')) if data.get('longitude') else None,
            mikrotik_device_id=data.get('mikrotik_device_id') or None,
            customer_id=data.get('customer_id') or None,
        )
        log_audit('CREATE', 'JobTicket', ticket.id, request.user, summary=f"Created {ticket.get_ticket_type_display()} ticket {ticket.ticket_number}")
        return JsonResponse({'success': True, 'ticket_id': ticket.id, 'ticket_number': ticket.ticket_number})
    except Exception as e:
        logger.error(f"Error creating ticket: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_assign_ticket(request, ticket_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        team_id = data.get('team_id')
        tech_ids = data.get('technician_ids', [])
        scheduled_date = data.get('scheduled_date')
        scheduled_time = data.get('scheduled_time', '').strip()
        remarks = data.get('remarks', '').strip()
        start_now = data.get('start_now', False)
        
        ticket.team_id = team_id if team_id else None
        if tech_ids:
            ticket.technicians.set(tech_ids)
        if scheduled_date:
            ticket.scheduled_date = scheduled_date
        if scheduled_time:
            ticket.scheduled_time = scheduled_time
        if remarks:
            ticket.remarks = remarks
            
        if start_now:
            ticket.status = 'IN_PROGRESS'
            ticket.time_start = timezone.now()
        else:
            ticket.status = 'ASSIGNED'
            
        ticket.save()
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=f"Assigned ticket {ticket.ticket_number} to team/technicians")
        return JsonResponse({'success': True, 'status': ticket.status, 'status_display': ticket.get_status_display()})
    except Exception as e:
        logger.error(f"Error assigning ticket: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_update_status(request, ticket_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        new_status = data.get('status')
        if new_status not in dict(JobTicket.STATUS_CHOICES):
            return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
            
        old_status = ticket.status
        ticket.status = new_status
        if new_status == 'IN_PROGRESS' and not ticket.time_start:
            ticket.time_start = timezone.now()
        elif new_status == 'COMPLETED' and not ticket.done_at:
            ticket.done_at = timezone.now()
            ticket.time_accomplish = timezone.now()
            if ticket.time_start:
                delta = ticket.time_accomplish - ticket.time_start
                ticket.duration = int(delta.total_seconds() / 60)
                ticket.done_duration = ticket.duration
                
        ticket.save()
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=f"Changed status from {old_status} to {new_status}")
        return JsonResponse({'success': True, 'status': ticket.status, 'status_display': ticket.get_status_display()})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_undispatch_ticket(request, ticket_id):
    """
    API endpoint: Reverts an Assigned or In-Progress JobTicket back to Pending.
    Clears assigned team and technicians, resets timers, and writes a history audit log.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    if ticket.status in ['ASSIGNED', 'IN_PROGRESS']:
        old_status = ticket.status
        old_team_name = ticket.team.name if ticket.team else 'Unassigned'
        ticket.status = 'PENDING'
        ticket.team = None
        ticket.technicians.clear()
        ticket.time_start = None
        ticket.save()

        JobTicketHistory.objects.create(
            job_ticket=ticket,
            actor=request.user,
            from_status=old_status,
            to_status='PENDING',
            note=f"Undispatched via API by {request.user.get_full_name() or request.user.username}. Removed from {old_team_name} and returned to Pending assignment queue."
        )
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=f"Undispatched ticket {ticket.ticket_number} (reverted to PENDING)")
        return JsonResponse({
            'success': True,
            'message': f'Ticket {ticket.ticket_number} undispatched and moved back to Pending queue.',
            'status': ticket.status,
            'status_display': ticket.get_status_display()
        })
    return JsonResponse({
        'success': False,
        'error': f'Ticket {ticket.ticket_number} is in {ticket.status} status and cannot be undispatched.'
    }, status=400)


@login_required
def api_update_location(request, ticket_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        lat = float(data.get('latitude'))
        lng = float(data.get('longitude'))
        ticket.latitude = lat
        ticket.longitude = lng
        ticket.save(update_fields=['latitude', 'longitude', 'updated_at'])
        
        # If linked to customer, sync customer coordinates as well
        if ticket.customer:
            ticket.customer.latitude = lat
            ticket.customer.longitude = lng
            ticket.customer.save(update_fields=['latitude', 'longitude'])
            
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=f"Updated GPS coords for {ticket.ticket_number}: ({lat}, {lng})")
        return JsonResponse({'success': True, 'latitude': lat, 'longitude': lng})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_complete_job(request, ticket_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        
        ticket.nap_port = data.get('nap_port', '').strip()
        ticket.cable_length = data.get('cable_length', '').strip()
        ticket.nap_reading = data.get('nap_reading', '').strip()
        ticket.pole_number = data.get('pole_number', '').strip()
        ticket.ont_modem_sn = data.get('ont_modem_sn', '').strip()
        ticket.signal_level = data.get('signal_level', '').strip()
        ticket.facility = data.get('facility', '').strip()
        ticket.house_reading = data.get('house_reading', '').strip()
        ticket.technician_remarks = data.get('technician_remarks', '').strip()
        ticket.acknowledged_by = data.get('acknowledged_by', '').strip()
        
        ticket.status = 'COMPLETED'
        ticket.time_accomplish = timezone.now()
        ticket.done_at = timezone.now()
        if ticket.time_start:
            delta = ticket.time_accomplish - ticket.time_start
            ticket.duration = int(delta.total_seconds() / 60)
            ticket.done_duration = ticket.duration
            
        ticket.save()
        
        # SMART CRM INTEGRATION:
        # If this was a New Installation ticket linked to a customer, transition the customer to Installed & Active
        if ticket.ticket_type == 'INSTALLATION' and ticket.customer:
            cust = ticket.customer
            cust.installation_status = 'installed'
            cust.status = 'active'
            if ticket.ont_modem_sn and not cust.mac_address:
                cust.mac_address = ticket.ont_modem_sn
            cust.save(update_fields=['installation_status', 'status', 'mac_address'])
            logger.info(f"[DISPATCH] Promoted Customer {cust.full_name} (ID: {cust.id}) to Active / Installed upon ticket completion.")
            
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=f"Completed Job Ticket {ticket.ticket_number}")
        return JsonResponse({'success': True, 'ticket_number': ticket.ticket_number, 'status': 'COMPLETED'})
    except Exception as e:
        logger.error(f"Error completing ticket: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ─────────────────────────────────────────────
# TAB & LEGACY SUPPORT VIEWS
# ─────────────────────────────────────────────

@login_required
def dispatch_monitoring_view(request):
    if request.method == 'POST':
        form = DispatchRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.csr = request.user
            record.save()
            form.save_m2m()
            log_audit('CREATE', 'DispatchRecord', record.id, request.user, summary=f"Created Dispatch Record for {record.client_name}")
            messages.success(request, 'Dispatch record added successfully!')
            return redirect('dispatch_monitoring')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DispatchRecordForm(initial={'date': timezone.now().date()})
    
    records = DispatchRecord.objects.all().order_by('-date')
    job_tickets = JobTicket.objects.all().select_related('customer', 'team').prefetch_related('technicians').order_by('-created_at')

    pending_tickets = job_tickets.filter(status='PENDING')
    ongoing_tickets = job_tickets.filter(status__in=['ASSIGNED', 'IN_PROGRESS'])
    completed_tickets = job_tickets.filter(status__in=['COMPLETED', 'QA_PASSED'])
    cancelled_tickets = job_tickets.filter(status='CANCELLED')

    pending_count = pending_tickets.count()
    ongoing_count = ongoing_tickets.count()
    completed_count = completed_tickets.count() + records.count()
    cancelled_count = cancelled_tickets.count()
    total_count = job_tickets.count() + records.count()

    teams = Team.objects.all()
    technicians = Technician.objects.all()

    return render(request, 'dispatch/dispatch_monitoring.html', {
        'records': records,
        'job_tickets': job_tickets,
        'pending_tickets': pending_tickets,
        'ongoing_tickets': ongoing_tickets,
        'completed_tickets': completed_tickets,
        'pending_count': pending_count,
        'ongoing_count': ongoing_count,
        'completed_count': completed_count,
        'cancelled_count': cancelled_count,
        'total_count': total_count,
        'teams': teams,
        'technicians': technicians,
        'form': form,
        'tab_type': 'ALL',
        'queue_name': 'Master Dispatch & Operations Log',
    })


def _handle_monitoring_view(request, tab_type, template_name):
    if request.method == 'POST':
        form = MonitoringRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.tab_type = tab_type
            record.csr = request.user
            record.save()
            form.save_m2m()
            log_audit('CREATE', 'MonitoringRecord', record.id, request.user, summary=f"Created Monitoring Record for {record.client_name} ({tab_type})")
            messages.success(request, 'Record added successfully!')
            return redirect(request.path)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = MonitoringRecordForm(initial={'tab_type': tab_type, 'date': timezone.now().date()})
    
    records = MonitoringRecord.objects.filter(tab_type=tab_type).select_related('status_option', 'customer').prefetch_related('teams').order_by('-date')
    job_tickets = JobTicket.objects.filter(source_tab=tab_type).select_related('customer', 'team').prefetch_related('technicians').order_by('-created_at')

    # PDF Page 10: Pending (not yet dispatched) vs Ongoing (currently being worked on)
    pending_tickets = job_tickets.filter(status='PENDING')
    ongoing_tickets = job_tickets.filter(status__in=['ASSIGNED', 'IN_PROGRESS'])
    completed_tickets = job_tickets.filter(status__in=['COMPLETED', 'QA_PASSED'])
    cancelled_tickets = job_tickets.filter(status='CANCELLED')

    pending_records = records.filter(Q(status_option__label__icontains='Pending') | Q(status_option__isnull=True, done_at__isnull=True))
    ongoing_records = records.filter(Q(status_option__label__icontains='Ongoing') | Q(status_option__label__icontains='Progress') | Q(time_start__isnull=False, done_at__isnull=True))
    completed_records = records.filter(Q(status_option__label__icontains='Done') | Q(done_at__isnull=False))
    cancelled_records = records.filter(status_option__label__icontains='Cancelled')

    pending_count = pending_tickets.count() + pending_records.count()
    ongoing_count = ongoing_tickets.count() + ongoing_records.count()
    completed_count = completed_tickets.count() + completed_records.count()
    cancelled_count = cancelled_tickets.count() + cancelled_records.count()
    total_count = records.count() + job_tickets.count()

    teams = Team.objects.all()
    technicians = Technician.objects.all()

    queue_labels = {
        'INTERNET_INSTALL': 'Internet Installation Queue',
        'CIGNAL_PLAY': 'Cignal Play Installation Queue',
        'CLIENT_CONCERNS': 'Client Concerns & Repairs Queue',
    }

    return render(request, template_name, {
        'records': records,
        'job_tickets': job_tickets,
        'pending_tickets': pending_tickets,
        'ongoing_tickets': ongoing_tickets,
        'completed_tickets': completed_tickets,
        'pending_records': pending_records,
        'ongoing_records': ongoing_records,
        'completed_records': completed_records,
        'pending_count': pending_count,
        'ongoing_count': ongoing_count,
        'completed_count': completed_count,
        'cancelled_count': cancelled_count,
        'total_count': total_count,
        'teams': teams,
        'technicians': technicians,
        'form': form,
        'tab_type': tab_type,
        'queue_name': queue_labels.get(tab_type, 'Dispatch Queue'),
    })


@login_required
def internet_install_view(request):
    return _handle_monitoring_view(request, 'INTERNET_INSTALL', 'dispatch/internet_install.html')


@login_required
def cignal_install_view(request):
    return _handle_monitoring_view(request, 'CIGNAL_PLAY', 'dispatch/cignal_install.html')


@login_required
def client_concerns_view(request):
    return _handle_monitoring_view(request, 'CLIENT_CONCERNS', 'dispatch/client_concerns.html')


@login_required
def complete_job_view(request, record_id):
    record = get_object_or_404(MonitoringRecord, id=record_id)
    job_detail, created = JobDetail.objects.get_or_create(record=record)
    
    if request.method == 'POST':
        form = JobDetailForm(request.POST, instance=job_detail)
        if form.is_valid():
            form.save()
            done_option = ConfigOption.objects.filter(module='MONITORING', list_type='STATUS', label__icontains='Done').first()
            if done_option:
                record.status_option = done_option
                record.save()
                
            # Smart CRM promotion hook
            if record.customer and record.tab_type == 'INTERNET_INSTALL':
                cust = record.customer
                cust.installation_status = 'installed'
                cust.status = 'active'
                if job_detail.ont_modem_sn and not cust.mac_address:
                    cust.mac_address = job_detail.ont_modem_sn
                cust.save(update_fields=['installation_status', 'status', 'mac_address'])
                
            log_audit('UPDATE', 'JobDetail', job_detail.id, request.user, summary=f"Completed Job for {record.client_name}")
            messages.success(request, 'Job details saved and marked as Done.')
            if record.tab_type == 'INTERNET_INSTALL':
                return redirect('internet_install')
            elif record.tab_type == 'CIGNAL_PLAY':
                return redirect('cignal_install')
            return redirect('client_concerns')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = JobDetailForm(instance=job_detail)
    return render(request, 'dispatch/complete_job.html', {'form': form, 'record': record})


@login_required
def audit_log_view(request):
    action_filter = request.GET.get('action', 'ALL').strip().upper()
    entity_filter = request.GET.get('entity', 'ALL').strip()
    search_q = request.GET.get('q', '').strip()

    qs = AuditLog.objects.select_related('actor').order_by('-created_at')

    # Summary KPI stats
    base_qs = AuditLog.objects.all()
    total_events = base_qs.count()
    creates_count = base_qs.filter(action='CREATE').count()
    updates_count = base_qs.filter(action='UPDATE').count()
    deletes_count = base_qs.filter(action='DELETE').count()

    if action_filter and action_filter != 'ALL':
        qs = qs.filter(action=action_filter)

    if entity_filter and entity_filter != 'ALL':
        qs = qs.filter(entity_type=entity_filter)

    if search_q:
        qs = qs.filter(
            Q(summary__icontains=search_q) |
            Q(entity_type__icontains=search_q) |
            Q(actor__username__icontains=search_q)
        )

    logs = qs[:150]

    # Distinct entity types for dropdown filter
    available_entities = sorted(list(set(AuditLog.objects.values_list('entity_type', flat=True).distinct())))

    return render(request, 'dispatch/audit_log.html', {
        'logs': logs,
        'action_filter': action_filter,
        'entity_filter': entity_filter,
        'search_q': search_q,
        'total_events': total_events,
        'creates_count': creates_count,
        'updates_count': updates_count,
        'deletes_count': deletes_count,
        'available_entities': available_entities,
    })


@login_required
def management_view(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    teams = Team.objects.prefetch_related('members').all()
    technicians = Technician.objects.select_related('team').all()
    accounts = User.objects.filter(is_active=True).order_by('-date_joined')

    # Aggregate target statistics
    total_daily_target = sum(t.target_per_day or 5 for t in technicians)
    total_monthly_target = sum(t.target_per_month or 100 for t in technicians)

    # Auto-seed baseline options if table is empty
    if not ConfigOption.objects.filter(module='DISPATCH').exists():
        defaults = [
            ('DISPATCH', 'STATUS', 'Pending', '#f59e0b', 1, True),
            ('DISPATCH', 'STATUS', 'Assigned', '#3b82f6', 2, False),
            ('DISPATCH', 'STATUS', 'In Progress', '#06b6d4', 3, False),
            ('DISPATCH', 'STATUS', 'Done', '#10b981', 4, True),
            ('DISPATCH', 'STATUS', 'Cancelled', '#ef4444', 5, True),
            ('DISPATCH', 'TYPE', 'Installation', '#10b981', 1, True),
            ('DISPATCH', 'TYPE', 'Repair', '#ef4444', 2, True),
            ('DISPATCH', 'TYPE', 'Cignal', '#a855f7', 3, False),
            ('DISPATCH', 'TYPE', 'Migration', '#06b6d4', 4, False),
            ('MONITORING', 'CHAT_TYPE', 'Inquiry', '#3b82f6', 1, True),
            ('MONITORING', 'CHAT_TYPE', 'Concern', '#f59e0b', 2, True),
            ('MONITORING', 'CHAT_TYPE', 'Follow-up', '#6366f1', 3, False),
        ]
        for mod, ltype, lbl, clr, sorder, hcode in defaults:
            ConfigOption.objects.get_or_create(
                module=mod, list_type=ltype, label=lbl,
                defaults={'color': clr, 'sort_order': sorder, 'active': True, 'hardcoded': hcode}
            )

    config_options = ConfigOption.objects.all().order_by('module', 'list_type', 'sort_order')
    locked_labels = {'done', 'cancelled', 'pending', 'installation', 'repair', 'concern', 'inquiry'}
    for opt in config_options:
        opt.is_locked = opt.hardcoded or (opt.label.strip().lower() in locked_labels)

    return render(request, 'dispatch/management.html', {
        'teams': teams,
        'technicians': technicians,
        'accounts': accounts,
        'total_daily_target': total_daily_target,
        'total_monthly_target': total_monthly_target,
        'config_options': config_options,
    })


@login_required
def export_tickets_csv(request):
    """
    Export Dispatch tickets to CSV matching legacy DMS columns:
    Ticket #, Status, Date Created, Date Completed, Turnaround, Client, Address, Barangay, Contact, Type, Concern, Team, Technicians
    Filtered by date, type, status, source_tab, or search query.
    """
    today = timezone.now().date()
    qs = JobTicket.objects.select_related('customer', 'team').prefetch_related('technicians')

    date_filter = request.GET.get('date_range', 'all')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    status_filter = request.GET.get('status', 'ALL')
    type_filter = request.GET.get('type', 'ALL')
    source_tab_filter = request.GET.get('source_tab', 'ALL')
    search_q = request.GET.get('q', '').strip()
    month = request.GET.get('month', '')

    if month and month.isdigit():
        qs = qs.filter(created_at__month=int(month), created_at__year=today.year)
    elif date_filter == 'today':
        qs = qs.filter(created_at__date=today)
    elif date_filter == 'this_month':
        qs = qs.filter(created_at__year=today.year, created_at__month=today.month)
    elif date_filter == 'custom' and date_from and date_to:
        qs = qs.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)

    if status_filter != 'ALL':
        qs = qs.filter(status=status_filter)
    if type_filter != 'ALL':
        qs = qs.filter(ticket_type=type_filter)
    if source_tab_filter != 'ALL':
        if source_tab_filter == 'CLIENT_CONCERNS':
            qs = qs.filter(Q(source_tab='CLIENT_CONCERNS') | Q(chat_type__icontains='concern'))
        else:
            qs = qs.filter(source_tab=source_tab_filter)
    if search_q:
        qs = qs.filter(
            Q(ticket_number__icontains=search_q) |
            Q(client_name__icontains=search_q) |
            Q(contact_number__icontains=search_q) |
            Q(address__icontains=search_q) |
            Q(barangay__icontains=search_q)
        )

    response = HttpResponse(content_type='text/csv')
    timestamp_str = timezone.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="dispatch_tickets_{timestamp_str}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Ticket #', 'Status', 'Date Created', 'Date Completed', 'Turnaround',
        'Client Name', 'Address', 'Barangay', 'Contact', 'Type', 'Concern',
        'Assigned Team', 'Technicians', 'Signal (dBm)', 'Modem SN'
    ])

    for t in qs.order_by('-created_at')[:5000]:
        techs_str = ", ".join(tech.name for tech in t.technicians.all())
        created_str = t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else ''
        done_str = t.done_at.strftime('%Y-%m-%d %H:%M') if t.done_at else ''
        writer.writerow([
            t.ticket_number,
            t.get_status_display(),
            created_str,
            done_str,
            t.turnaround_display,
            t.client_name,
            t.address or '',
            t.barangay or '',
            t.contact_number or '',
            t.get_ticket_type_display(),
            t.concern or '',
            t.team.name if t.team else 'Unassigned',
            techs_str,
            t.signal_level or '',
            t.ont_modem_sn or ''
        ])

    return response


@login_required
@require_POST
def api_delete_ticket(request, ticket_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    ticket = get_object_or_404(JobTicket, id=ticket_id)
    ticket_num = ticket.ticket_number
    ticket.delete()
    log_audit('DELETE', 'JobTicket', ticket_id, request.user, summary=f"Deleted ticket {ticket_num}")
    return JsonResponse({'success': True, 'message': f"Ticket {ticket_num} deleted successfully."})


# --- Phase 3 APIs: Customer Autofill & Duplicate Name Lockout ---

@login_required
def api_customer_search(request):
    """
    Live customer search endpoint for real-time autofill.
    Searches by name, phone, address, and pppoe_username.
    """
    q = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 10))
    if not q or len(q) < 2:
        return JsonResponse({'success': True, 'customers': []})

    from billing.models import Customer
    from django.db.models import Q

    customers = Customer.objects.filter(
        Q(full_name__icontains=q) |
        Q(phone__icontains=q) |
        Q(address__icontains=q) |
        Q(pppoe_username__icontains=q)
    ).select_related('barangay', 'plan')[:limit]

    results = []
    for c in customers:
        results.append({
            'id': c.id,
            'name': c.full_name,
            'phone': c.phone or '',
            'address': c.address or '',
            'barangay': c.barangay.name if c.barangay else '',
            'barangay_id': c.barangay_id,
            'plan_name': c.plan.name if c.plan else '',
            'plan_id': c.plan_id,
            'pppoe_username': c.pppoe_username or '',
            'latitude': c.latitude,
            'longitude': c.longitude,
            'account_no': getattr(c, 'account_number', c.pppoe_username or ''),
        })
    return JsonResponse({'success': True, 'customers': results})


@login_required
def api_customer_check_name(request):
    """
    Real-time duplicate customer name verification.
    Triggers red-border lockout on client forms if unconfirmed exact match is detected.
    """
    name = request.GET.get('name', '').strip()
    exclude_id = request.GET.get('exclude_id')
    if not name:
        return JsonResponse({'success': True, 'exists': False})

    from billing.models import Customer
    qs = Customer.objects.filter(full_name__iexact=name)
    if exclude_id and str(exclude_id).isdigit():
        qs = qs.exclude(id=int(exclude_id))

    existing = qs.first()
    return JsonResponse({
        'success': True,
        'exists': existing is not None,
        'customer_id': existing.id if existing else None,
        'customer_name': existing.full_name if existing else None,
        'phone': existing.phone if existing else '',
        'address': existing.address if existing else ''
    })


# --- Phase 3 APIs: Dynamic Dropdown Config Manager ---

LOCKED_SYSTEM_LABELS = {'done', 'cancelled', 'pending', 'installation', 'repair', 'concern', 'inquiry'}

@login_required
@require_POST
def api_config_options_create(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
    label = data.get('label', '').strip()
    module = data.get('module', 'MONITORING').strip().upper()
    list_type = data.get('list_type', 'STATUS').strip().upper()
    color = data.get('color', '#6b7280').strip()
    active = data.get('active', True)
    if isinstance(active, str):
        active = active.lower() in ('true', '1', 'yes')

    if not label:
        return JsonResponse({'success': False, 'error': 'Label is required.'}, status=400)
    if module not in ['DISPATCH', 'MONITORING']:
        return JsonResponse({'success': False, 'error': 'Invalid module.'}, status=400)
    if list_type not in ['STATUS', 'TYPE', 'CHAT_TYPE']:
        return JsonResponse({'success': False, 'error': 'Invalid list type.'}, status=400)

    if ConfigOption.objects.filter(module=module, list_type=list_type, label__iexact=label).exists():
        return JsonResponse({'success': False, 'error': f'An option with label "{label}" already exists in {module} {list_type}.'}, status=400)

    max_order = ConfigOption.objects.filter(module=module, list_type=list_type).aggregate(Max('sort_order'))['sort_order__max'] or 0
    opt = ConfigOption.objects.create(
        module=module,
        list_type=list_type,
        label=label,
        color=color,
        sort_order=max_order + 1,
        active=active,
        hardcoded=False
    )
    log_audit('CREATE', 'ConfigOption', opt.id, request.user, summary=f"Created {module} {list_type} option: {label}", after={'label': label, 'color': color, 'active': active})
    return JsonResponse({
        'success': True,
        'option': {
            'id': opt.id, 'module': opt.module, 'list_type': opt.list_type,
            'label': opt.label, 'color': opt.color, 'active': opt.active, 'hardcoded': opt.hardcoded
        }
    })


@login_required
@require_POST
def api_config_options_update(request, option_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    opt = get_object_or_404(ConfigOption, id=option_id)
    data = json.loads(request.body.decode('utf-8')) if request.body else request.POST

    is_locked = opt.hardcoded or (opt.label.strip().lower() in LOCKED_SYSTEM_LABELS)
    before_data = {'label': opt.label, 'color': opt.color, 'active': opt.active}

    new_label = data.get('label', '').strip()
    if new_label and not is_locked:
        if ConfigOption.objects.filter(module=opt.module, list_type=opt.list_type, label__iexact=new_label).exclude(id=opt.id).exists():
            return JsonResponse({'success': False, 'error': f'An option with label "{new_label}" already exists.'}, status=400)
        opt.label = new_label

    if 'color' in data:
        opt.color = str(data['color']).strip()

    if 'active' in data:
        val = data['active']
        if isinstance(val, str):
            opt.active = val.lower() in ('true', '1', 'yes')
        else:
            opt.active = bool(val)

    opt.save()
    after_data = {'label': opt.label, 'color': opt.color, 'active': opt.active}
    log_audit('UPDATE', 'ConfigOption', opt.id, request.user, summary=f"Updated config option #{opt.id} ({opt.label})", before=before_data, after=after_data)

    return JsonResponse({
        'success': True,
        'option': {
            'id': opt.id, 'module': opt.module, 'list_type': opt.list_type,
            'label': opt.label, 'color': opt.color, 'active': opt.active, 'hardcoded': is_locked
        }
    })


@login_required
@require_POST
def api_config_options_delete(request, option_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    opt = get_object_or_404(ConfigOption, id=option_id)
    if opt.hardcoded or (opt.label.strip().lower() in LOCKED_SYSTEM_LABELS):
        return JsonResponse({'success': False, 'error': f'"{opt.label}" is a system-critical option and cannot be deleted. You can recolor it or toggle active.'}, status=400)

    label = opt.label
    opt.delete()
    log_audit('DELETE', 'ConfigOption', option_id, request.user, summary=f"Deleted custom config option: {label}")
    return JsonResponse({'success': True, 'message': f'Option "{label}" deleted successfully.'})


# ---------------------------------------------------------------------------
# Feature: No-Contact Escalation Workflow
# ---------------------------------------------------------------------------

@login_required
def api_log_contact_attempt(request, ticket_id):
    """
    POST /dispatch/api/tickets/<id>/contact-attempt/
    Increments the contact_attempt_count (max 3) and writes a history note.
    Available to technicians and dispatchers on the pipeline view.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    if ticket.contact_attempt_count >= 3:
        return JsonResponse({'success': False, 'error': 'Maximum 3 contact attempts already logged.', 'count': 3})

    ticket.contact_attempt_count = ticket.contact_attempt_count + 1
    ticket.save(update_fields=['contact_attempt_count', 'updated_at'])

    JobTicketHistory.objects.create(
        job_ticket=ticket,
        actor=request.user,
        from_status=ticket.status,
        to_status=ticket.status,
        note=f"Contact attempt #{ticket.contact_attempt_count} logged by {request.user.get_full_name() or request.user.username}. Client did not respond."
    )
    log_audit('UPDATE', 'JobTicket', ticket.id, request.user,
              summary=f"Contact attempt #{ticket.contact_attempt_count} logged for {ticket.ticket_number}")
    return JsonResponse({'success': True, 'count': ticket.contact_attempt_count})


@login_required
def api_mark_unreachable(request, ticket_id):
    """
    POST /dispatch/api/tickets/<id>/mark-unreachable/
    Cancels the ticket with a specified reason (no_contact, change_of_mind, undecided, other).
    Intended for dispatchers after technician escalates a no-contact situation.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, Exception):
        data = request.POST

    reason = data.get('reason', 'no_contact')
    valid_reasons = dict(JobTicket.CANCELLATION_REASON_CHOICES)
    if reason not in valid_reasons:
        return JsonResponse({'success': False, 'error': 'Invalid cancellation reason.'}, status=400)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    old_status = ticket.status
    ticket.status = 'CANCELLED'
    ticket.cancellation_reason = reason
    ticket.save(update_fields=['status', 'cancellation_reason', 'updated_at'])

    JobTicketHistory.objects.create(
        job_ticket=ticket,
        actor=request.user,
        from_status=old_status,
        to_status='CANCELLED',
        note=f"Closed by dispatcher ({request.user.get_full_name() or request.user.username}): {valid_reasons[reason]}"
    )
    log_audit('UPDATE', 'JobTicket', ticket.id, request.user,
              summary=f"Ticket {ticket.ticket_number} marked unreachable — {valid_reasons[reason]}")
    return JsonResponse({'success': True, 'reason_display': valid_reasons[reason]})


# ---------------------------------------------------------------------------
# Feature: Post-Installation Welcome SMS
# ---------------------------------------------------------------------------

def _send_installation_welcome_sms(ticket):
    """
    Sends portal login credentials via SMS to the customer linked to the ticket.
    No URL links included per NTC regulations (URLs are blocked in PH SMS).
    """
    customer = ticket.customer
    if not customer or not customer.phone:
        return False, "No customer or phone linked to this ticket."

    login_id = customer.pppoe_username or customer.account_no or customer.phone
    portal_pw = customer.portal_password or "(see dispatcher)"

    msg = (
        f"Welcome to Gametech Unli Fiber! "
        f"For easy payment, billing statement, etc, access your portal online account.\n\n"
        f"Your account info:\n"
        f"Login: {login_id}\n"
        f"Password: {portal_pw}\n"
        f"Access site: type gametech.com.ph in your browser"
    )
    from billing.views import send_semaphore_sms
    _, success = send_semaphore_sms(customer.phone, msg)
    return success, msg


@login_required
def api_send_welcome_sms(request, ticket_id):
    """
    POST /dispatch/api/tickets/<id>/send-welcome-sms/
    Manually triggered by dispatcher on Stage 5 Approval to send portal credentials SMS.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    success, result = _send_installation_welcome_sms(ticket)
    if not success:
        return JsonResponse({'success': False, 'error': result})

    log_audit('ACTION', 'JobTicket', ticket.id, request.user,
              summary=f"Welcome SMS sent to customer for ticket {ticket.ticket_number}")
    JobTicketHistory.objects.create(
        job_ticket=ticket,
        actor=request.user,
        from_status=ticket.status,
        to_status=ticket.status,
        note=f"Portal welcome SMS sent to {ticket.customer.phone} by {request.user.get_full_name() or request.user.username}"
    )
    return JsonResponse({'success': True, 'message': 'Welcome SMS sent successfully.'})
