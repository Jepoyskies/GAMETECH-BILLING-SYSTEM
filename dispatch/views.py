import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from billing.models import Customer
from network_manager.models import MikrotikDevice
from .models import (
    JobTicket, DispatchRecord, MonitoringRecord, JobDetail,
    ConfigOption, Technician, Team, AuditLog
)
from .forms import MonitoringRecordForm, DispatchRecordForm, JobDetailForm

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
    return redirect('dispatch_dashboard')


@login_required
def dashboard_view(request):
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
    search_q = request.GET.get('q', '').strip()
    
    tickets_qs = JobTicket.objects.select_related('customer', 'team', 'mikrotik_device').prefetch_related('technicians')
    
    if status_filter != 'ALL':
        tickets_qs = tickets_qs.filter(status=status_filter)
    if type_filter != 'ALL':
        tickets_qs = tickets_qs.filter(ticket_type=type_filter)
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
            'concern': t.concern or '',
            'assigned_team': t.team.name if t.team else 'Unassigned',
            'scheduled_date': t.scheduled_date.strftime('%b %d, %Y') if t.scheduled_date else 'Not scheduled',
        })
        
    context = {
        'pending_verification_count': pending_verification_count,
        'awaiting_assignment_count': awaiting_assignment_count,
        'active_in_field_count': active_in_field_count,
        'pending_qa_approval_count': pending_qa_approval_count,
        'total_techs_count': total_techs_count,
        'tickets': tickets,
        'teams': teams,
        'technicians': technicians,
        'mikrotik_devices': mikrotik_devices,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search_q': search_q,
        'map_points_json': json.dumps(map_points),
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
            if str(sales_agent_val).isdigit():
                agent_obj = Agent.objects.filter(id=int(sales_agent_val)).first()
            if not agent_obj:
                agent_obj = Agent.objects.filter(name__iexact=str(sales_agent_val).strip()).first()
        
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

        ticket = JobTicket.objects.create(
            client_name=client_name,
            address=data.get('address', '').strip(),
            barangay=data.get('barangay', '').strip(),
            contact_number=data.get('contact_number', '').strip(),
            account_no=data.get('account_no', '').strip(),
            sales_agent=agent_obj,
            is_test_data=is_test,
            plan_package=data.get('plan_package', '').strip(),
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
    return render(request, 'dispatch/dispatch_monitoring.html', {'records': records, 'job_tickets': job_tickets, 'form': form})


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
    
    records = MonitoringRecord.objects.filter(tab_type=tab_type).order_by('-date')
    job_tickets = JobTicket.objects.filter(source_tab=tab_type).select_related('customer', 'team').prefetch_related('technicians').order_by('-created_at')
    return render(request, template_name, {
        'records': records,
        'job_tickets': job_tickets,
        'form': form,
        'tab_type': tab_type
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
    logs = AuditLog.objects.select_related('actor').order_by('-created_at')[:100]
    return render(request, 'dispatch/audit_log.html', {'logs': logs})


@login_required
def management_view(request):
    teams = Team.objects.all()
    technicians = Technician.objects.select_related('team').all()
    config_options = ConfigOption.objects.all().order_by('module', 'list_type', 'sort_order')
    return render(request, 'dispatch/management.html', {
        'teams': teams,
        'technicians': technicians,
        'config_options': config_options
    })
