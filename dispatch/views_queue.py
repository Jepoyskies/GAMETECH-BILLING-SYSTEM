import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.models import User

from dispatch.models import JobTicket, JobTicketHistory, Team, Technician, AuditLog
from billing.models import Customer, Notification

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
            after_data=after,
        )
    except Exception as e:
        logger.warning(f"Failed to record dispatch audit log: {e}")


@login_required
def dispatch_queue_view(request):
    """
    Main Dispatch Queue:
    Replaces the draft Stage 1 & 2 pages with a responsive, multi-tab queue.
    New tickets arrive UNASSIGNED in status 'PENDING'.
    """
    ticket_type_filter = request.GET.get('type', 'ALL')
    search_query = request.GET.get('q', '').strip()
    active_tab = request.GET.get('tab', 'unassigned')

    base_qs = JobTicket.objects.select_related(
        'customer', 'mikrotik_device', 'sales_agent', 'team'
    ).prefetch_related('technicians')

    if ticket_type_filter != 'ALL':
        base_qs = base_qs.filter(ticket_type=ticket_type_filter)

    if search_query:
        base_qs = base_qs.filter(
            Q(ticket_number__icontains=search_query) |
            Q(client_name__icontains=search_query) |
            Q(contact_number__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(barangay__icontains=search_query) |
            Q(concern__icontains=search_query)
        )

    # Tab 1: Unassigned tickets (new install job orders, repairs, site visits)
    unassigned_tickets = base_qs.filter(
        status='PENDING',
        team__isnull=True,
    ).order_by('-created_at')

    # Tab 2: Assigned & In-Progress jobs
    ongoing_tickets = base_qs.filter(
        status__in=['ASSIGNED', 'IN_PROGRESS']
    ).order_by('-created_at')

    # Tab 3: Attention needed (3+ contact attempts, unreachable, or bounced)
    attention_tickets = base_qs.filter(
        Q(contact_attempt_count__gte=3) |
        Q(cancellation_reason__isnull=False) |
        Q(bounce_count__gte=1) |
        Q(same_person_flag=True)
    ).order_by('-updated_at')

    # Tab 4: Completed & Approval Pipeline
    completed_tickets = base_qs.filter(
        status__in=['COMPLETED', 'QA_PASSED', 'APPROVED', 'CANCELLED']
    ).order_by('-updated_at')[:60]

    # Available teams and ON-DUTY technicians for assignment
    teams = Team.objects.prefetch_related('members').all()
    on_duty_technicians = Technician.objects.filter(is_available=True).select_related('team')
    all_technicians = Technician.objects.select_related('team').all()

    context = {
        'unassigned_tickets': unassigned_tickets,
        'ongoing_tickets': ongoing_tickets,
        'attention_tickets': attention_tickets,
        'completed_tickets': completed_tickets,
        'unassigned_count': unassigned_tickets.count(),
        'ongoing_count': ongoing_tickets.count(),
        'attention_count': attention_tickets.count(),
        'completed_count': completed_tickets.count(),
        'teams': teams,
        'on_duty_technicians': on_duty_technicians,
        'all_technicians': all_technicians,
        'ticket_type_filter': ticket_type_filter,
        'search_query': search_query,
        'active_tab': active_tab,
    }
    return render(request, "dispatch/pipeline/queue.html", context)


@login_required
def api_assign_ticket(request, ticket_id):
    """
    POST /dispatch/api/tickets/<id>/assign/
    Assigns ticket to a Team (auto-assigns on-duty members) or individual on-duty technicians.
    Off-duty technicians are strictly excluded.
    Technicians are prohibited from self-assigning / picking jobs.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    # Permission check: Field technicians without dispatch/staff roles cannot assign/pick tickets
    is_dispatcher = (
        request.user.is_staff or
        request.user.is_superuser or
        request.user.has_perm('dispatch.assign_technicians') or
        getattr(request.user, 'role', '') in ['Admin', 'Staff', 'CSR', 'Dispatch']
    )
    if not is_dispatcher:
        return JsonResponse({
            'success': False,
            'error': 'Permission denied: Technicians are not allowed to assign or self-pick jobs.'
        }, status=403)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        team_id = data.get('team_id')
        tech_ids = data.get('technician_ids', [])
        scheduled_date = data.get('scheduled_date')
        scheduled_time = data.get('scheduled_time', '').strip()
        remarks = data.get('remarks', '').strip()

        old_status = ticket.status
        if not ticket.can_transition_to('ASSIGNED'):
            return JsonResponse({
                'success': False,
                'error': f"Cannot transition ticket from '{old_status}' to 'ASSIGNED'."
            }, status=400)

        # 1. Resolve Team and Technicians (Filter strictly by is_available=True)
        assigned_techs = []
        if team_id:
            team = get_object_or_404(Team, id=team_id)
            ticket.team = team
            # Auto-assign all ON-DUTY members of the team
            on_duty_team_members = team.members.filter(is_available=True)
            assigned_techs = list(on_duty_team_members)
        else:
            ticket.team = None

        if tech_ids:
            # If specific technicians selected, ensure they are ON-DUTY
            selected_techs = Technician.objects.filter(id__in=tech_ids, is_available=True)
            for t in selected_techs:
                if t not in assigned_techs:
                    assigned_techs.append(t)

        if not assigned_techs and not team_id:
            return JsonResponse({
                'success': False,
                'error': 'No on-duty technicians available in the selection. Please select an active team or on-duty technician.'
            }, status=400)

        ticket.technicians.set(assigned_techs)

        if scheduled_date:
            ticket.scheduled_date = scheduled_date
        if scheduled_time:
            ticket.scheduled_time = scheduled_time
        if remarks:
            ticket.remarks = remarks

        ticket.status = 'ASSIGNED'
        ticket.record_stage_action('ASSIGNMENT', request.user)
        ticket.save()

        tech_names = ", ".join([t.name for t in assigned_techs]) if assigned_techs else "Team"
        note = f"Assigned to {ticket.team.name if ticket.team else ''} ({tech_names}) by {request.user.get_full_name() or request.user.username}"
        JobTicketHistory.objects.create(
            job_ticket=ticket,
            actor=request.user,
            from_status=old_status,
            to_status='ASSIGNED',
            note=note,
        )
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=note)

        return JsonResponse({
            'success': True,
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
            'assigned_to': tech_names,
        })
    except Exception as e:
        logger.error(f"Error assigning ticket: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_toggle_technician_duty(request, tech_id):
    """
    POST /dispatch/api/technicians/<tech_id>/toggle-duty/
    Toggles a technician between On-Duty and Off-Duty.
    Off-duty technicians are excluded from job assignment offerings.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    tech = get_object_or_404(Technician, id=tech_id)
    tech.is_available = not tech.is_available
    tech.save(update_fields=['is_available', 'updated_at'])

    status_str = "On-Duty" if tech.is_available else "Off-Duty"
    log_audit('UPDATE', 'Technician', tech.id, request.user, summary=f"Marked technician {tech.name} as {status_str}")

    return JsonResponse({
        'success': True,
        'tech_id': tech.id,
        'name': tech.name,
        'is_available': tech.is_available,
        'status_display': status_str,
    })


@login_required
def api_correct_timer(request, ticket_id):
    """
    POST /dispatch/api/tickets/<ticket_id>/correct-timer/
    Dispatch can correct a forgotten arrived/done timer with a logged reason.
    Requires permission 'dispatch.correct_timers' or staff status.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    can_correct = (
        request.user.is_staff or
        request.user.is_superuser or
        request.user.has_perm('dispatch.correct_timers') or
        getattr(request.user, 'role', '') in ['Admin', 'Staff', 'Dispatch']
    )
    if not can_correct:
        return JsonResponse({'success': False, 'error': 'Permission denied: Cannot correct job timers.'}, status=403)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        reason = (data.get('reason') or '').strip()
        if not reason:
            return JsonResponse({'success': False, 'error': 'A mandatory reason is required to correct a timer.'}, status=400)

        arrived_at_str = data.get('arrived_at')
        finished_at_str = data.get('finished_at')

        from django.utils.dateparse import parse_datetime
        if arrived_at_str:
            parsed_arrived = parse_datetime(arrived_at_str)
            if parsed_arrived:
                if timezone.is_naive(parsed_arrived):
                    parsed_arrived = timezone.make_aware(parsed_arrived)
                ticket.arrived_at = parsed_arrived
                ticket.time_start = parsed_arrived

        if finished_at_str:
            parsed_finished = parse_datetime(finished_at_str)
            if parsed_finished:
                if timezone.is_naive(parsed_finished):
                    parsed_finished = timezone.make_aware(parsed_finished)
                ticket.finished_at = parsed_finished
                ticket.time_accomplish = parsed_finished

        # Recalculate duration in minutes if both timestamps exist
        if ticket.arrived_at and ticket.finished_at:
            delta = ticket.finished_at - ticket.arrived_at
            ticket.duration = max(0, int(delta.total_seconds() // 60))
            ticket.done_duration = ticket.duration

        ticket.timer_corrected_at = timezone.now()
        ticket.timer_corrected_by = request.user
        ticket.timer_correction_reason = reason
        ticket.record_stage_action('TIMER_CORRECTED', request.user)
        ticket.save()

        note = f"Timer corrected by {request.user.username}. Reason: {reason}"
        JobTicketHistory.objects.create(
            job_ticket=ticket,
            actor=request.user,
            from_status=ticket.status,
            to_status=ticket.status,
            note=note,
        )
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=note)

        return JsonResponse({
            'success': True,
            'duration': ticket.duration,
            'arrived_at': ticket.arrived_at.isoformat() if ticket.arrived_at else None,
            'finished_at': ticket.finished_at.isoformat() if ticket.finished_at else None,
            'reason': reason,
        })
    except Exception as e:
        logger.error(f"Error correcting timer: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_undispatch_ticket(request, ticket_id):
    """
    POST /dispatch/api/tickets/<ticket_id>/undispatch/
    Reverts an assigned ticket back to unassigned PENDING status.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    if ticket.status not in ['ASSIGNED', 'IN_PROGRESS']:
        return JsonResponse({'success': False, 'error': f"Ticket in status '{ticket.status}' cannot be undispatched."}, status=400)

    old_status = ticket.status
    ticket.status = 'PENDING'
    ticket.team = None
    ticket.technicians.clear()
    ticket.time_start = None
    ticket.arrived_at = None
    ticket.save()

    note = f"Undispatched and returned to unassigned queue by {request.user.username}."
    JobTicketHistory.objects.create(
        job_ticket=ticket,
        actor=request.user,
        from_status=old_status,
        to_status='PENDING',
        note=note,
    )
    log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=note)

    return JsonResponse({
        'success': True,
        'status': ticket.status,
        'status_display': ticket.get_status_display(),
    })
