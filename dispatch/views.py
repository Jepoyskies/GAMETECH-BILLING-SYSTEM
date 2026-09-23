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
from .views_management import *

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
    cancellation_reason_filter = request.GET.get('cancellation_reason', 'ALL')
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
        if status_filter == 'ONGOING':
            tickets_qs = tickets_qs.filter(status__in=['ASSIGNED', 'IN_PROGRESS'])
        elif status_filter in ['CLOSED', 'COMPLETED', 'DONE']:
            tickets_qs = tickets_qs.filter(status__in=['COMPLETED', 'QA_PASSED'])
        else:
            tickets_qs = tickets_qs.filter(status=status_filter)

    if type_filter != 'ALL':
        if type_filter == 'REPAIR':
            tickets_qs = tickets_qs.filter(Q(ticket_type='REPAIR') | Q(source_tab='CLIENT_CONCERNS'))
        elif type_filter == 'INSTALLATION':
            tickets_qs = tickets_qs.filter(ticket_type='INSTALLATION')
        else:
            tickets_qs = tickets_qs.filter(ticket_type=type_filter)

    if source_tab_filter != 'ALL':
        if source_tab_filter == 'CLIENT_CONCERNS':
            tickets_qs = tickets_qs.filter(Q(source_tab='CLIENT_CONCERNS') | Q(ticket_type='REPAIR') | Q(chat_type__icontains='concern'))
        else:
            tickets_qs = tickets_qs.filter(source_tab=source_tab_filter)
    if team_filter != 'ALL' and team_filter.isdigit():
        tickets_qs = tickets_qs.filter(team_id=int(team_filter))
    if cancellation_reason_filter != 'ALL':
        tickets_qs = tickets_qs.filter(cancellation_reason=cancellation_reason_filter)
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
        'cancellation_reason_filter': cancellation_reason_filter,
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
    ticket = JobTicket.objects.select_related('customer', 'team', 'mikrotik_device', 'created_by', 'sales_agent').filter(id=ticket_id).first()
    record = None
    if not ticket:
        record = MonitoringRecord.objects.select_related('customer', 'status_option', 'type_option', 'chat_type_option', 'sales_agent', 'csr').prefetch_related('teams').filter(id=ticket_id).first()
        if not record:
            return JsonResponse({'success': False, 'error': f'Dispatch ticket #{ticket_id} not found.'}, status=404)

    if request.method == 'POST':
        import json
        from django.utils.dateparse import parse_date
        from django.utils import timezone
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        if ticket:
            if 'client_name' in data and data['client_name']:
                ticket.client_name = data['client_name'].strip()
            if 'contact_number' in data:
                ticket.contact_number = data['contact_number'].strip()
            if 'account_no' in data:
                ticket.account_no = data['account_no'].strip()
            if 'address' in data:
                ticket.address = data['address'].strip()
            if 'barangay' in data:
                ticket.barangay = data['barangay'].strip()
            if 'concern' in data:
                ticket.concern = data['concern'].strip()
            if 'ticket_type' in data and data['ticket_type']:
                ticket.ticket_type = data['ticket_type']
            if 'chat_type' in data:
                ticket.chat_type = data['chat_type']
            if 'status' in data and data['status']:
                ticket.status = data['status']
                if ticket.status in ['COMPLETED', 'QA_PASSED', 'COMPLETED_AND_VERIFIED'] and not ticket.done_at:
                    ticket.done_at = timezone.now()
            if 'source_tab' in data and data['source_tab']:
                ticket.source_tab = data['source_tab']
            if 'scheduled_date' in data and data['scheduled_date']:
                ticket.scheduled_date = parse_date(data['scheduled_date'])
            elif 'scheduled_date' in data and not data['scheduled_date']:
                ticket.scheduled_date = None
            if 'scheduled_time' in data:
                ticket.scheduled_time = data['scheduled_time']
            if 'nap_port' in data:
                ticket.nap_port = data['nap_port']
            if 'cable_length' in data:
                ticket.cable_length = data['cable_length']
            if 'nap_reading' in data:
                ticket.nap_reading = data['nap_reading']
            if 'pole_number' in data:
                ticket.pole_number = data['pole_number']
            if 'ont_modem_sn' in data:
                ticket.ont_modem_sn = data['ont_modem_sn']
            if 'signal_level' in data:
                ticket.signal_level = data['signal_level']
            if 'facility' in data:
                ticket.facility = data['facility']
            if 'house_reading' in data:
                ticket.house_reading = data['house_reading']
            if 'special_instruction' in data:
                ticket.special_instruction = data['special_instruction']
            if 'technician_remarks' in data:
                ticket.technician_remarks = data['technician_remarks']
            if 'remarks' in data:
                ticket.remarks = data['remarks']
            if 'acknowledged_by' in data:
                ticket.acknowledged_by = data['acknowledged_by']
            if 'actions_taken' in data:
                ticket.actions_taken = data['actions_taken']
            if 'ticket_number' in data and data['ticket_number']:
                ticket.ticket_number = data['ticket_number'].strip()
            ticket.save()

            if 'technician_ids' in data:
                ticket.technicians.set(data['technician_ids'])

            if 'email_address' in data and ticket.customer:
                email_val = data['email_address'].strip()
                if email_val != ticket.customer.email:
                    ticket.customer.email = email_val
                    ticket.customer.save(update_fields=['email'])

            log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=f"Updated Dispatch #{ticket.id} ({ticket.client_name})")
            return JsonResponse({'success': True, 'message': 'Ticket updated successfully!'})
        elif record:
            if 'client_name' in data and data['client_name']:
                record.client_name = data['client_name'].strip()
            if 'contact_number' in data:
                record.contact_number = data['contact_number'].strip()
            if 'address' in data:
                record.address = data['address'].strip()
            if 'concern' in data:
                record.concern = data['concern'].strip()
            if 'actions_taken' in data:
                record.actions_taken = data['actions_taken']
            if 'remarks' in data:
                record.remarks = data['remarks']
            record.save()

            if 'technician_ids' in data:
                record.teams.set(data['technician_ids'])

            job_detail, _ = JobDetail.objects.get_or_create(record=record)
            for fld in ['nap_port', 'cable_length', 'nap_reading', 'pole_number', 'ont_modem_sn',
                        'signal_level', 'facility', 'house_reading', 'special_instruction',
                        'technician_remarks', 'acknowledged_by', 'account_no', 'email_address']:
                if fld in data:
                    setattr(job_detail, fld, data[fld])
            if 'barangay' in data:
                job_detail.barangay_city = data['barangay']
            if 'scheduled_date' in data and data['scheduled_date']:
                job_detail.schedule_date = parse_date(data['scheduled_date'])
            if 'scheduled_time' in data:
                job_detail.schedule_time = data['scheduled_time']
            job_detail.save()

            log_audit('UPDATE', 'MonitoringRecord', record.id, request.user, summary=f"Updated Dispatch #{record.id} ({record.client_name})")
            return JsonResponse({'success': True, 'message': 'Record updated successfully!'})

    teams_data = []
    for tm in Team.objects.prefetch_related('members').order_by('name'):
        members_list = [{'id': m.id, 'name': m.name} for m in tm.members.all().order_by('name')]
        teams_data.append({
            'id': tm.id,
            'name': tm.name,
            'members': members_list
        })
    unassigned = Technician.objects.filter(team__isnull=True).order_by('name')
    if unassigned.exists():
        teams_data.append({
            'id': 0,
            'name': 'Other Technicians',
            'members': [{'id': m.id, 'name': m.name} for m in unassigned]
        })

    if ticket:
        ticket_data = {
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'client_name': ticket.client_name,
            'address': ticket.address or '',
            'barangay': ticket.barangay or '',
            'contact_number': ticket.contact_number or '',
            'alternate_contact': ticket.alternate_contact or '',
            'account_no': ticket.account_no or '',
            'email_address': ticket.customer.email if ticket.customer and ticket.customer.email else '',
            'sales_agent': ticket.sales_agent.name if ticket.sales_agent else '',
            'csr': (ticket.created_by.get_full_name() or ticket.created_by.username) if ticket.created_by else 'Joseph Alberto',
            'concern': ticket.concern or '',
            'remarks': ticket.remarks or '',
            'special_instruction': ticket.special_instruction or '',
            'actions_taken': ticket.actions_taken or '',
            'ticket_type': ticket.ticket_type,
            'ticket_type_display': ticket.get_ticket_type_display(),
            'chat_type': ticket.chat_type or 'Concern',
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
            'source_tab': ticket.source_tab,
            'source_tab_display': ticket.get_source_tab_display(),
            'priority': ticket.priority,
            'team_id': ticket.team_id,
            'team_name': ticket.team.name if ticket.team else None,
            'technician_ids': list(ticket.technicians.values_list('id', flat=True)),
            'technicians': [tech.name for tech in ticket.technicians.all()],
            'scheduled_date': ticket.scheduled_date.isoformat() if ticket.scheduled_date else '',
            'scheduled_time': ticket.scheduled_time or '',
            'nap_port': ticket.nap_port or '',
            'cable_length': ticket.cable_length or '',
            'nap_reading': ticket.nap_reading or '',
            'pole_number': ticket.pole_number or '',
            'ont_modem_sn': ticket.ont_modem_sn or '',
            'signal_level': ticket.signal_level or '',
            'facility': ticket.facility or '',
            'house_reading': ticket.house_reading or '',
            'technician_remarks': ticket.technician_remarks or '',
            'acknowledged_by': ticket.acknowledged_by or '',
            'time_start': ticket.time_start.strftime('%m/%d/%Y %I:%M %p') if ticket.time_start else '',
            'time_accomplish': ticket.time_accomplish.strftime('%m/%d/%Y %I:%M %p') if ticket.time_accomplish else '',
            'done_at': ticket.done_at.strftime('%m/%d/%Y %I:%M %p') if ticket.done_at else '',
            'duration': f"{ticket.duration}m" if ticket.duration else '',
            'turnaround_display': ticket.turnaround_display,
            'job_order_no': ticket.ticket_number,
            'created_at': ticket.created_at.strftime('%m/%d/%Y %I:%M %p'),
            'completed_at': (ticket.done_at or ticket.time_accomplish).strftime('%m/%d/%Y %I:%M %p') if (ticket.done_at or ticket.time_accomplish) else '',
        }
    else:
        jd = getattr(record, 'job_detail', None)
        ticket_data = {
            'id': record.id,
            'ticket_number': record.ticket_number or f"GPT-{record.id:07d}",
            'client_name': record.client_name,
            'address': record.address or '',
            'barangay': jd.barangay_city if jd and jd.barangay_city else '',
            'contact_number': record.contact_number or '',
            'alternate_contact': record.alternate_contact or '',
            'account_no': jd.account_no if jd and jd.account_no else '',
            'email_address': jd.email_address if jd and jd.email_address else (record.customer.email if record.customer and record.customer.email else ''),
            'sales_agent': record.sales_agent.name if record.sales_agent else '',
            'csr': (record.csr.get_full_name() or record.csr.username) if record.csr else 'Joseph Alberto',
            'concern': record.concern or '',
            'remarks': record.remarks or '',
            'special_instruction': jd.special_instruction if jd and jd.special_instruction else '',
            'actions_taken': record.actions_taken or '',
            'ticket_type': record.type_option.label if record.type_option else 'Repair',
            'ticket_type_display': record.type_option.label if record.type_option else 'Repair',
            'chat_type': record.chat_type_option.label if record.chat_type_option else 'Concern',
            'status': record.status_option.label if record.status_option else 'Done',
            'status_display': record.status_option.label if record.status_option else 'Done',
            'source_tab': record.source_tab or 'CLIENT_CONCERNS',
            'source_tab_display': record.get_source_tab_display() if hasattr(record, 'get_source_tab_display') else (record.source_tab or 'CLIENT_CONCERNS'),
            'priority': 'NORMAL',
            'team_id': None,
            'team_name': None,
            'technician_ids': list(record.teams.values_list('id', flat=True)),
            'technicians': [tech.name for tech in record.teams.all()],
            'scheduled_date': jd.schedule_date.isoformat() if jd and jd.schedule_date else '',
            'scheduled_time': jd.schedule_time if jd and jd.schedule_time else '',
            'nap_port': jd.nap_port if jd and jd.nap_port else '',
            'cable_length': jd.cable_length if jd and jd.cable_length else '',
            'nap_reading': jd.nap_reading if jd and jd.nap_reading else '',
            'pole_number': jd.pole_number if jd and jd.pole_number else '',
            'ont_modem_sn': jd.ont_modem_sn if jd and jd.ont_modem_sn else '',
            'signal_level': jd.signal_level if jd and jd.signal_level else '',
            'facility': jd.facility if jd and jd.facility else '',
            'house_reading': jd.house_reading if jd and jd.house_reading else '',
            'technician_remarks': jd.technician_remarks if jd and jd.technician_remarks else '',
            'acknowledged_by': jd.acknowledged_by if jd and jd.acknowledged_by else '',
            'time_start': record.time_start.strftime('%m/%d/%Y %I:%M %p') if record.time_start else '',
            'time_accomplish': record.time_accomplish.strftime('%m/%d/%Y %I:%M %p') if record.time_accomplish else '',
            'done_at': record.done_at.strftime('%m/%d/%Y %I:%M %p') if record.done_at else '',
            'duration': f"{record.duration}m" if record.duration else '',
            'turnaround_display': f"{record.duration}m" if record.duration else '-',
            'job_order_no': jd.job_order if jd and jd.job_order else (record.ticket_number or f"GPT-{record.id:07d}"),
            'created_at': record.date.strftime('%m/%d/%Y %I:%M %p') if hasattr(record, 'date') and hasattr(record.date, 'strftime') else '',
            'completed_at': (record.done_at or record.time_accomplish).strftime('%m/%d/%Y %I:%M %p') if (record.done_at or record.time_accomplish) else '',
        }

    return JsonResponse({
        'success': True,
        'ticket': ticket_data,
        'teams': teams_data,
    })


@login_required
def api_create_ticket(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        client_name = data.get('client_name', '').strip()
            
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
        if not cust_id:
            return JsonResponse({
                'success': False,
                'error': 'A registered CRM customer is required. Dispatch job orders can only be created for existing customers.'
            }, status=400)

        from billing.models import Customer
        cust = Customer.objects.filter(id=cust_id).first()
        if not cust:
            return JsonResponse({
                'success': False,
                'error': 'The selected customer could not be found in the database. Please select a valid customer.'
            }, status=400)

        if not client_name:
            client_name = cust.full_name

        is_test = getattr(cust, 'is_test_data', False)
        if not agent_obj and cust.agent:
            agent_obj = cust.agent
        if agent_obj and getattr(agent_obj, 'is_test_data', False):
            is_test = True

        raw_pay_method = data.get('payment_method', 'CASH').upper()
        if raw_pay_method not in ['CASH', 'GCASH', 'BANK_TRANSFER', 'OTHER']:
            raw_pay_method = 'CASH'

        raw_ticket_type = data.get('ticket_type', 'INSTALLATION').upper()
        # Automatically resolve source_tab based on ticket_type if not explicitly supplied
        source_tab = data.get('source_tab')
        if not source_tab:
            if raw_ticket_type in ['REPAIR', 'RELOCATION', 'RECONNECTION', 'DISCONNECTION']:
                source_tab = 'CLIENT_CONCERNS'
            elif raw_ticket_type == 'CIGNAL':
                source_tab = 'CIGNAL_PLAY'
            else:
                source_tab = 'INTERNET_INSTALL'

        lat_val = data.get('latitude')
        if not lat_val and cust.latitude:
            lat_val = cust.latitude
        lng_val = data.get('longitude')
        if not lng_val and cust.longitude:
            lng_val = cust.longitude

        ticket = JobTicket.objects.create(
            client_name=client_name,
            address=data.get('address', '').strip() or (cust.address or ''),
            barangay=data.get('barangay', '').strip() or (cust.barangay.name if cust.barangay else ''),
            contact_number=data.get('contact_number', '').strip() or (cust.phone or ''),
            account_no=data.get('account_no', '').strip() or (cust.pppoe_username or ''),
            sales_agent=agent_obj,
            is_test_data=is_test,
            plan_package=data.get('plan_package', '').strip() or (cust.plan.name if cust.plan else ''),
            payment_method=raw_pay_method,
            ticket_type=raw_ticket_type,
            source_tab=source_tab,
            priority=data.get('priority', 'NORMAL'),
            status='PENDING',
            concern=data.get('concern', '').strip(),
            remarks=data.get('remarks', '').strip(),
            special_instruction=data.get('special_instruction', '').strip(),
            created_by=request.user,
            latitude=float(lat_val) if lat_val else None,
            longitude=float(lng_val) if lng_val else None,
            mikrotik_device_id=data.get('mikrotik_device_id') or cust.mikrotik_device_id,
            customer_id=cust.id,
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
            
        if ticket.status == 'CANCELLED' and new_status != 'CANCELLED':
            return JsonResponse({
                'success': False,
                'error': 'Cancelled tickets cannot be re-opened per dispatch policy. Please create a new ticket if the client returns.'
            }, status=400)
            
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
            
        # Synchronize any matching open MonitoringRecords for this customer
        if ticket.customer:
            done_opt = ConfigOption.objects.filter(list_type='STATUS', label__icontains='Done').first()
            MonitoringRecord.objects.filter(
                customer=ticket.customer,
                done_at__isnull=True
            ).update(
                done_at=timezone.now(),
                status_option=done_opt
            )

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
    
    records = MonitoringRecord.objects.all().select_related('status_option', 'customer').prefetch_related('teams').order_by('-date')
    job_tickets = JobTicket.objects.all().select_related('customer', 'team').prefetch_related('technicians').order_by('-created_at')

    pending_tickets = job_tickets.filter(status='PENDING')
    ongoing_tickets = job_tickets.filter(status__in=['ASSIGNED', 'IN_PROGRESS'])
    completed_tickets = job_tickets.filter(status__in=['COMPLETED', 'QA_PASSED', 'COMPLETED_AND_VERIFIED'])
    cancelled_tickets = job_tickets.filter(status='CANCELLED')

    completed_records = records.filter(Q(status_option__label__icontains='Done') | Q(status_option__label__icontains='Completed') | Q(done_at__isnull=False))
    cancelled_records = records.filter(status_option__label__icontains='Cancelled')
    ongoing_records = records.exclude(id__in=completed_records).exclude(id__in=cancelled_records).filter(
        Q(status_option__label__icontains='Ongoing') | Q(status_option__label__icontains='Progress') | Q(time_start__isnull=False)
    )
    pending_records = records.exclude(id__in=completed_records).exclude(id__in=cancelled_records).exclude(id__in=ongoing_records)

    pending_count = pending_tickets.count() + pending_records.count()
    ongoing_count = ongoing_tickets.count() + ongoing_records.count()
    completed_count = completed_tickets.count() + completed_records.count()
    cancelled_count = cancelled_tickets.count() + cancelled_records.count()
    total_count = records.count() + job_tickets.count()

    teams = Team.objects.all()
    technicians = Technician.objects.all()

    return render(request, 'dispatch/dispatch_monitoring.html', {
        'records': records,
        'job_tickets': job_tickets,
        'pending_tickets': pending_tickets,
        'ongoing_tickets': ongoing_tickets,
        'completed_tickets': completed_tickets,
        'cancelled_tickets': cancelled_tickets,
        'pending_records': pending_records,
        'ongoing_records': ongoing_records,
        'completed_records': completed_records,
        'cancelled_records': cancelled_records,
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
    
    records = MonitoringRecord.objects.filter(tab_type=tab_type).select_related(
        'status_option', 'customer', 'csr', 'type_option', 'job_detail'
    ).prefetch_related('teams').order_by('-date', '-created_at')
    job_tickets = JobTicket.objects.filter(source_tab=tab_type).select_related('customer', 'team').prefetch_related('technicians').order_by('-created_at')

    # --- Filter: CSR ---
    csr_filter = request.GET.get('csr', 'ALL')
    if csr_filter and csr_filter != 'ALL':
        try:
            records = records.filter(csr__id=int(csr_filter))
        except (ValueError, TypeError):
            pass

    # --- Filter: Status (matches ConfigOption label) ---
    status_filter = request.GET.get('status', 'ALL')
    if status_filter and status_filter != 'ALL':
        records = records.filter(status_option__label__iexact=status_filter)

    # PDF Page 10: Pending (not yet dispatched) vs Ongoing (currently being worked on)
    pending_tickets = job_tickets.filter(status='PENDING')
    ongoing_tickets = job_tickets.filter(status__in=['ASSIGNED', 'IN_PROGRESS'])
    completed_tickets = job_tickets.filter(status__in=['COMPLETED', 'QA_PASSED', 'COMPLETED_AND_VERIFIED'])
    cancelled_tickets = job_tickets.filter(status='CANCELLED')

    completed_records = records.filter(Q(status_option__label__icontains='Done') | Q(status_option__label__icontains='Completed') | Q(done_at__isnull=False))
    cancelled_records = records.filter(status_option__label__icontains='Cancelled')
    ongoing_records = records.exclude(id__in=completed_records).exclude(id__in=cancelled_records).filter(
        Q(status_option__label__icontains='Ongoing') | Q(status_option__label__icontains='Progress') | Q(time_start__isnull=False)
    )
    pending_records = records.exclude(id__in=completed_records).exclude(id__in=cancelled_records).exclude(id__in=ongoing_records)

    pending_count = pending_tickets.count() + pending_records.count()
    ongoing_count = ongoing_tickets.count() + ongoing_records.count()
    completed_count = completed_tickets.count() + completed_records.count()
    cancelled_count = cancelled_tickets.count() + cancelled_records.count()
    total_count = records.count() + job_tickets.count()

    teams = Team.objects.all()
    technicians = Technician.objects.all()

    # CSRs who have records in this tab (for filter dropdown)
    csr_ids = MonitoringRecord.objects.filter(tab_type=tab_type).values_list('csr_id', flat=True).distinct()
    csrs = User.objects.filter(id__in=csr_ids).order_by('first_name', 'last_name', 'username')

    # Status options for filter dropdown (MONITORING module)
    status_options = ConfigOption.objects.filter(list_type='STATUS', module='MONITORING', active=True).order_by('sort_order', 'label')

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
        'csrs': csrs,
        'status_options': status_options,
        'csr_filter': csr_filter,
        'status_filter': status_filter,
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
            done_option = ConfigOption.objects.filter(list_type='STATUS', label__icontains='Done').first()
            if done_option:
                record.status_option = done_option
            record.done_at = timezone.now()
            record.save()
                
            # Smart CRM promotion hook
            if record.customer:
                cust = record.customer
                if record.tab_type == 'INTERNET_INSTALL':
                    cust.installation_status = 'installed'
                    cust.status = 'active'
                if job_detail.ont_modem_sn and not cust.mac_address:
                    cust.mac_address = job_detail.ont_modem_sn
                cust.save()

                # Sync any open JobTicket for this customer so the entire pipeline advances
                open_ticket = JobTicket.objects.filter(
                    customer=cust,
                    status__in=['PENDING', 'ASSIGNED', 'IN_PROGRESS']
                ).first()
                if open_ticket:
                    open_ticket.status = 'COMPLETED'
                    open_ticket.done_at = timezone.now()
                    if job_detail.ont_modem_sn:
                        open_ticket.ont_modem_sn = job_detail.ont_modem_sn
                    if job_detail.signal_level:
                        open_ticket.signal_level = job_detail.signal_level
                    if job_detail.nap_port:
                        open_ticket.nap_port = job_detail.nap_port
                    if job_detail.cable_length:
                        open_ticket.cable_length = job_detail.cable_length
                    if job_detail.pole_number:
                        open_ticket.pole_number = job_detail.pole_number
                    if job_detail.nap_reading:
                        open_ticket.nap_reading = job_detail.nap_reading
                    if job_detail.house_reading:
                        open_ticket.house_reading = job_detail.house_reading
                    if job_detail.facility:
                        open_ticket.facility = job_detail.facility
                    if job_detail.technician_remarks:
                        open_ticket.technician_remarks = job_detail.technician_remarks
                    if job_detail.acknowledged_by:
                        open_ticket.acknowledged_by = job_detail.acknowledged_by
                    open_ticket.save()
                    JobTicketHistory.objects.create(
                        job_ticket=open_ticket,
                        actor=request.user,
                        from_status='IN_PROGRESS',
                        to_status='COMPLETED',
                        note=f"Completed via Monitoring Record #{record.id}. Ready for QA."
                    )
                
            log_audit('UPDATE', 'JobDetail', job_detail.id, request.user, summary=f"Completed Job for {record.client_name}")
            messages.success(request, f"Job details for {record.client_name} saved and marked as Done.")
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
    ticket = get_object_or_404(JobTicket, id=ticket_id)
    if ticket.status in ['COMPLETED', 'QA_PASSED', 'COMPLETED_AND_VERIFIED']:
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'success': False, 'error': 'Only administrators are authorized to delete completed Job Orders.'}, status=403)
    ticket_num = ticket.ticket_number
    ticket.delete()
    log_audit('DELETE', 'JobTicket', ticket_id, request.user, summary=f"Deleted ticket {ticket_num}")
    return JsonResponse({'success': True, 'message': f"Ticket {ticket_num} deleted successfully."})


@login_required
@require_POST
def api_delete_record(request, record_id):
    record = get_object_or_404(MonitoringRecord, id=record_id)
    if record.done_at or (record.status_option and 'Done' in getattr(record.status_option, 'label', '')):
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'success': False, 'error': 'Only administrators are authorized to delete completed records.'}, status=403)
    client_name = record.client_name
    record.delete()
    log_audit('DELETE', 'MonitoringRecord', record_id, request.user, summary=f"Deleted monitoring record #{record_id} for {client_name}")
    return JsonResponse({'success': True, 'message': f"Record #{record_id} deleted successfully."})


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
    ).select_related('barangay', 'plan', 'mikrotik_device')[:limit]

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
            'mikrotik_device_id': c.mikrotik_device_id or '',
            'mikrotik_name': c.mikrotik_device.device_name if c.mikrotik_device else '',
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


@login_required
def job_order_print_view(request, ticket_id=None):
    """
    Renders the official Gametech ISP Job Order Form (Installation / Repair Service)
    formatted for standard Letter/A4 printing and PDF generation.
    If ticket_id is None or 0, renders a blank printable copy.
    """
    ticket = None
    is_installation = False
    is_repair = False
    team_and_techs = ""
    tech_signatures = ""
    customer_email = ""
    prepared_by_name = ""
    finish_time = None

    if ticket_id and int(ticket_id) > 0:
        ticket = get_object_or_404(
            JobTicket.objects.select_related('customer', 'team', 'created_by').prefetch_related('technicians'),
            id=ticket_id
        )
        is_installation = ticket.ticket_type == 'INSTALLATION'
        is_repair = ticket.ticket_type in ['REPAIR', 'CLIENT_CONCERNS']

        # Format Assigned Crew & Technicians
        tech_list = [t.name for t in ticket.technicians.all()]
        crew_parts = []
        if ticket.team:
            crew_parts.append(ticket.team.name)
        if tech_list:
            crew_parts.append(", ".join(tech_list))
        team_and_techs = " - ".join(crew_parts) if crew_parts else ""
        tech_signatures = ", ".join(tech_list) if tech_list else (ticket.team.name if ticket.team else "")

        # Customer Email resolution
        if ticket.customer and ticket.customer.email:
            customer_email = ticket.customer.email

        # Prepared By
        if ticket.created_by:
            prepared_by_name = ticket.created_by.get_full_name() or ticket.created_by.username

        # Finish time
        finish_time = ticket.time_accomplish or ticket.done_at

    return render(request, "dispatch/job_order_print.html", {
        "ticket": ticket,
        "is_installation": is_installation,
        "is_repair": is_repair,
        "team_and_techs": team_and_techs,
        "tech_signatures": tech_signatures,
        "customer_email": customer_email,
        "prepared_by_name": prepared_by_name,
        "finish_time": finish_time,
    })


@login_required
def job_order_print_record_view(request, record_id):
    """
    Fallback printable view for legacy MonitoringRecord entries.
    """
    record = get_object_or_404(MonitoringRecord.objects.select_related('customer').prefetch_related('teams'), id=record_id)
    detail = getattr(record, 'job_detail', None)

    is_installation = record.tab_type == 'INTERNET_INSTALL'
    is_repair = record.tab_type == 'CLIENT_CONCERNS'
    team_names = ", ".join([t.name for t in record.teams.all()])

    class LegacyRecordAdapter:
        ticket_number = detail.job_order if detail and detail.job_order else f"REC-{record.id}"
        created_at = record.created_at if hasattr(record, 'created_at') else timezone.now()
        ticket_type = 'INSTALLATION' if is_installation else 'REPAIR'
        client_name = record.client_name
        account_no = detail.account_no if detail and detail.account_no else (record.customer.pppoe_username if record.customer else "")
        contact_number = record.contact_number
        address = record.address
        barangay = detail.barangay_city if detail and detail.barangay_city else (record.customer.barangay.name if record.customer and record.customer.barangay else "")
        scheduled_date = detail.schedule_date if detail else None
        scheduled_time = detail.schedule_time if detail else None
        plan_package = detail.plan_package if detail and detail.plan_package else (record.customer.plan.name if record.customer and record.customer.plan else "")
        nap_port = detail.nap_port if detail else ""
        ont_modem_sn = detail.ont_modem_sn if detail else ""
        cable_length = detail.cable_length if detail else ""
        signal_level = detail.signal_level if detail else ""
        latitude = getattr(record.customer, 'latitude', None) if record.customer else None
        longitude = getattr(record.customer, 'longitude', None) if record.customer else None
        facility = detail.facility if detail else ""
        nap_reading = detail.nap_reading if detail else ""
        house_reading = detail.house_reading if detail else ""
        pole_number = detail.pole_number if detail else ""
        concern = record.concern
        actions_taken = record.remarks or ""
        special_instruction = detail.special_instruction if detail else ""
        time_start = None
        time_accomplish = record.done_at
        done_at = record.done_at
        technician_remarks = detail.technician_remarks if detail else ""
        acknowledged_by = detail.acknowledged_by if detail else ""

    ticket_adapter = LegacyRecordAdapter()
    customer_email = detail.email_address if detail and detail.email_address else (record.customer.email if record.customer else "")

    return render(request, "dispatch/job_order_print.html", {
        "ticket": ticket_adapter,
        "is_installation": is_installation,
        "is_repair": is_repair,
        "team_and_techs": team_names,
        "tech_signatures": team_names,
        "customer_email": customer_email,
        "prepared_by_name": request.user.get_full_name() or request.user.username,
        "finish_time": record.done_at,
    })


# ─── Monitoring Record Quick-Action APIs ───────────────────────────────────────

@login_required
@require_POST
def api_monitoring_dispatch(request, record_id):
    """Assign a team + schedule to a MonitoringRecord → moves it to Ongoing tab."""
    record = get_object_or_404(MonitoringRecord, id=record_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = {}
    team_id = data.get('team_id')
    schedule_date = data.get('schedule_date') or None
    schedule_time = data.get('schedule_time') or None

    if team_id:
        try:
            tech = Technician.objects.get(id=int(team_id))
            record.teams.set([tech])
        except (Technician.DoesNotExist, ValueError):
            pass

    ongoing_opt = ConfigOption.objects.filter(list_type='STATUS', module='MONITORING', label__icontains='Ongoing').first()
    if ongoing_opt:
        record.status_option = ongoing_opt
    record.time_start = timezone.now()
    record.save()

    job_detail, _ = JobDetail.objects.get_or_create(record=record)
    if schedule_date:
        try:
            from datetime import date as _date
            job_detail.schedule_date = _date.fromisoformat(schedule_date)
        except ValueError:
            pass
    if schedule_time:
        job_detail.schedule_time = schedule_time
    job_detail.save()

    log_audit('UPDATE', 'MonitoringRecord', record.id, request.user, summary=f"Dispatched {record.client_name}")
    return JsonResponse({'success': True})


@login_required
@require_POST
def api_monitoring_undispatch(request, record_id):
    """Return a MonitoringRecord to Pending status."""
    record = get_object_or_404(MonitoringRecord, id=record_id)
    pending_opt = ConfigOption.objects.filter(list_type='STATUS', module='MONITORING', label__icontains='Pending').first()
    if pending_opt:
        record.status_option = pending_opt
    record.time_start = None
    record.save()
    log_audit('UPDATE', 'MonitoringRecord', record.id, request.user, summary=f"Undispatched {record.client_name}")
    return JsonResponse({'success': True})


@login_required
@require_POST
def api_monitoring_done(request, record_id):
    """Mark a MonitoringRecord as Done + sync CRM if internet install."""
    record = get_object_or_404(MonitoringRecord, id=record_id)
    done_opt = ConfigOption.objects.filter(list_type='STATUS', module='MONITORING', label__icontains='Done').first()
    if done_opt:
        record.status_option = done_opt
    record.done_at = timezone.now()
    record.save()

    if record.customer and record.tab_type == 'INTERNET_INSTALL':
        cust = record.customer
        cust.installation_status = 'installed'
        cust.status = 'active'
        cust.save()

    log_audit('UPDATE', 'MonitoringRecord', record.id, request.user, summary=f"Marked Done: {record.client_name}")
    return JsonResponse({'success': True})
