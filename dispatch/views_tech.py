import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone

from dispatch.models import JobTicket, JobTicketHistory, Technician, CallAttemptLog, AuditLog
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
def technician_mobile_view(request):
    """
    Step 3: Mobile-first field view for technicians.
    Rules:
    - Technicians see ONLY their assigned jobs (status in ['ASSIGNED', 'IN_PROGRESS']).
    - Technicians CANNOT pick or claim unassigned jobs.
    - Staff / Admin can preview as any technician.
    """
    tech = None
    is_staff = request.user.is_staff or request.user.is_superuser

    if hasattr(request.user, 'technician'):
        tech = request.user.technician
    else:
        tech = Technician.objects.filter(user=request.user).first()

    if not tech and is_staff:
        tech_id = request.GET.get('tech_id')
        if tech_id:
            tech = Technician.objects.filter(id=tech_id).first()
        if not tech:
            tech = Technician.objects.first()

    if not tech and not is_staff:
        messages.error(request, "Access restricted: You do not have an active Technician profile.")
        return redirect('dispatch_dashboard')

    if tech:
        assigned_tickets = JobTicket.objects.filter(
            technicians=tech,
            status__in=['ASSIGNED', 'IN_PROGRESS'],
        ).select_related('customer', 'team').prefetch_related('call_attempts').order_by('scheduled_date', 'scheduled_time')
    else:
        assigned_tickets = JobTicket.objects.filter(
            status__in=['ASSIGNED', 'IN_PROGRESS']
        ).select_related('customer', 'team').prefetch_related('call_attempts').order_by('scheduled_date', 'scheduled_time')

    active_ticket_id = request.GET.get('ticket_id')
    active_ticket = None
    if active_ticket_id:
        active_ticket = assigned_tickets.filter(id=active_ticket_id).first()
    if not active_ticket:
        active_ticket = assigned_tickets.first()

    all_techs = Technician.objects.all() if is_staff else None

    return render(request, "dispatch/pipeline/tech_mobile.html", {
        'technician': tech,
        'tickets': assigned_tickets,
        'ticket': active_ticket,
        'is_staff_preview': is_staff and not hasattr(request.user, 'technician'),
        'all_techs': all_techs,
    })


@login_required
def api_ticket_arrived(request, ticket_id):
    """
    POST /dispatch/api/tickets/<ticket_id>/arrived/
    Technician clicked Arrived: starts job timer.
    Optionally records GPS coordinates (latitude/longitude) if provided by browser.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    if not ticket.can_transition_to('IN_PROGRESS'):
        return JsonResponse({
            'success': False,
            'error': f"Ticket in status '{ticket.status}' cannot transition to Arrived (IN_PROGRESS)."
        }, status=400)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        lat_val = data.get('latitude') or data.get('arrival_latitude')
        lng_val = data.get('longitude') or data.get('arrival_longitude')

        if lat_val and lng_val:
            try:
                ticket.arrival_latitude = float(lat_val)
                ticket.arrival_longitude = float(lng_val)
            except (ValueError, TypeError):
                pass

        now = timezone.now()
        old_status = ticket.status
        ticket.arrived_at = now
        ticket.time_start = now
        ticket.status = 'IN_PROGRESS'
        ticket.record_stage_action('FIELD_ARRIVED', request.user)
        ticket.save()

        note = f"Technician arrived on site at {now.strftime('%I:%M %p')}. Timer started."
        if ticket.arrival_latitude and ticket.arrival_longitude:
            note += f" GPS: ({ticket.arrival_latitude:.5f}, {ticket.arrival_longitude:.5f})"

        JobTicketHistory.objects.create(
            job_ticket=ticket,
            actor=request.user,
            from_status=old_status,
            to_status='IN_PROGRESS',
            note=note,
        )
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=note)

        return JsonResponse({
            'success': True,
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
            'arrived_at': ticket.arrived_at.isoformat(),
            'has_gps': bool(ticket.arrival_latitude),
        })
    except Exception as e:
        logger.error(f"Error in api_ticket_arrived: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_ticket_done(request, ticket_id):
    """
    POST /dispatch/api/tickets/<ticket_id>/done/
    Technician clicked Done: stops job timer and submits completion report.
    Transitions:
    - SITE_VISIT: assign -> in_progress -> COMPLETED (done).
    - REPAIR / INSTALLATION: transitions to COMPLETED for QA.
    - Notifies staff via Notification bell.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    if not ticket.can_transition_to('COMPLETED'):
        return JsonResponse({
            'success': False,
            'error': f"Ticket in status '{ticket.status}' cannot transition to Done (COMPLETED)."
        }, status=400)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        now = timezone.now()
        old_status = ticket.status

        ticket.finished_at = now
        ticket.time_accomplish = now
        ticket.done_at = now

        # Calculate duration
        start_time = ticket.arrived_at or ticket.time_start
        if start_time:
            delta = now - start_time
            ticket.duration = max(1, int(delta.total_seconds() // 60))
            ticket.done_duration = ticket.duration

        # Form specs
        ticket.nap_port = (data.get('nap_port') or '').strip()
        ticket.cable_length = (data.get('cable_length') or '').strip()
        ticket.nap_reading = (data.get('nap_reading') or '').strip()
        ticket.pole_number = (data.get('pole_number') or '').strip()
        ticket.ont_modem_sn = (data.get('ont_modem_sn') or '').strip()
        ticket.signal_level = (data.get('signal_level') or '').strip()
        ticket.facility = (data.get('facility') or '').strip()
        ticket.house_reading = (data.get('house_reading') or '').strip()
        ticket.technician_report = (data.get('technician_report') or data.get('technician_remarks') or '').strip()
        ticket.acknowledged_by = (data.get('acknowledged_by') or '').strip()
        ticket.status = 'COMPLETED'
        ticket.record_stage_action('FIELD_DONE', request.user)
        ticket.save()

        # Wire SITE_VISIT (assign -> done)
        site_visit_note = " (Site Visit Complete)" if ticket.ticket_type == 'SITE_VISIT' else ""
        note = f"Technician marked job as Done{site_visit_note}. Timer stopped: {ticket.duration or 0} min(s)."
        JobTicketHistory.objects.create(
            job_ticket=ticket,
            actor=request.user,
            from_status=old_status,
            to_status='COMPLETED',
            note=note,
        )
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=note)

        # Notification: Technician Done -> Staff
        try:
            Notification.objects.create(
                title=f"Technician Done: {ticket.ticket_number}",
                message=f"Technician {request.user.get_full_name() or request.user.username} completed {ticket.get_ticket_type_display()} for {ticket.client_name}. Ready for QA review.",
                notification_type="dispatch",
                link=f"/dispatch/pipeline/queue/?tab=completed",
            )
        except Exception as e:
            logger.warning(f"Could not create completion notification: {e}")

        return JsonResponse({
            'success': True,
            'status': ticket.status,
            'duration': ticket.duration,
            'ticket_number': ticket.ticket_number,
        })
    except Exception as e:
        logger.error(f"Error in api_ticket_done: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_log_call_attempt(request, ticket_id):
    """
    POST /dispatch/api/tickets/<ticket_id>/contact-attempt/
    Logs client call attempt with outcome and notes.
    After 3 attempts or client refusal, returns can_return=True.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        result = data.get('result', 'unanswered')
        notes = (data.get('notes') or '').strip()

        tech = getattr(request.user, 'technician', None)
        if not tech:
            tech = Technician.objects.filter(user=request.user).first()

        new_count = ticket.contact_attempt_count + 1
        ticket.contact_attempt_count = new_count
        ticket.save(update_fields=['contact_attempt_count', 'updated_at'])

        CallAttemptLog.objects.create(
            ticket=ticket,
            technician=tech,
            attempt_number=new_count,
            result=result,
            notes=notes,
        )

        can_return = (new_count >= 3 or result == 'client_declined')
        note = f"Contact attempt #{new_count} logged ({result}): {notes}"
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
            'count': new_count,
            'can_return': can_return,
            'result': result,
        })
    except Exception as e:
        logger.error(f"Error logging call attempt: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_return_to_dispatch(request, ticket_id):
    """
    POST /dispatch/api/tickets/<ticket_id>/return-to-dispatch/
    After 3 contact attempts or client refusal, technician returns job to Dispatch.
    Notifies staff and marks customer 'Closed - Not Installed' if applicable.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        reason = data.get('reason', 'no_contact')
        notes = (data.get('notes') or '').strip()

        old_status = ticket.status
        ticket.status = 'CANCELLED'
        ticket.cancellation_reason = reason
        ticket.close_reason = 'Unreachable' if reason == 'no_contact' else 'Change of mind'
        ticket.close_reason_note = notes
        ticket.record_stage_action('RETURNED_UNREACHABLE', request.user)
        ticket.save()

        # Update customer state to Closed - Not Installed per Spec #12
        if ticket.customer:
            ticket.customer.installation_status = 'closed_not_installed'
            ticket.customer.save(update_fields=['installation_status', 'updated_at'])

        note = f"Job returned to Dispatch after {ticket.contact_attempt_count} attempt(s). Reason: {reason}. {notes}"
        JobTicketHistory.objects.create(
            job_ticket=ticket,
            actor=request.user,
            from_status=old_status,
            to_status='CANCELLED',
            note=note,
        )
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=note)

        # Notification: Job Returned Unreachable -> Staff
        try:
            Notification.objects.create(
                title=f"Job Returned Unreachable: {ticket.ticket_number}",
                message=f"Job for {ticket.client_name} returned to Dispatch after {ticket.contact_attempt_count} attempts ({reason}). Please inform sales agent.",
                notification_type="dispatch",
                link=f"/dispatch/pipeline/queue/?tab=attention",
            )
        except Exception as e:
            logger.warning(f"Could not create unreachable notification: {e}")

        return JsonResponse({
            'success': True,
            'status': ticket.status,
            'ticket_number': ticket.ticket_number,
            'reason': reason,
        })
    except Exception as e:
        logger.error(f"Error returning job to dispatch: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
