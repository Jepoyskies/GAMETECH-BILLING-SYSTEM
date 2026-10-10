"""
Technician handover (feature B).

JobTicket.technicians is a flat M2M and cannot express "this tech started, that
tech finished, and here is why". TicketTechnicianAssignment is the ordered
record. These helpers are the only place that writes it, so the ordering and
the mandatory-reason rule are enforced in exactly one place.

READ-ONLY NOTE: nothing here touches a MikroTik router. Dispatch records what
happened in the field; it never provisions, suspends, or modifies router state.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from django.db import models
from django.db.models import Max

from dispatch.models import (
    ConfigOption, JobTicket, JobTicketHistory, Technician, TicketTechnicianAssignment,
)
from dispatch.utils import log_audit

logger = logging.getLogger(__name__)

OTHER_REASON_MARKER = 'other'


def _parse_body(request):
    """
    Accepts both the JSON posts the mobile app sends and ordinary form posts
    from the dispatch screens. Branching on content type matters: reading
    request.body for a multipart form yields raw bytes that are not JSON.
    """
    if 'application/json' in (request.content_type or '').lower():
        if not request.body:
            return {}
        try:
            return json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return None
    return request.POST


def _get_ids(data, key):
    """
    Pull a list of ids out of either a QueryDict (form post) or a plain dict
    (JSON post).

    QueryDict.get() returns only the LAST value for a repeated key, and
    iterating a bare string of "12" would silently yield [1, 2]. getlist()
    avoids both traps.
    """
    if hasattr(data, 'getlist'):
        raw = data.getlist(key)
    else:
        raw = data.get(key)
        if raw is None:
            raw = []
        elif not isinstance(raw, (list, tuple)):
            raw = [raw]
    out = []
    for item in raw:
        text = str(item).strip()
        if text.isdigit():
            out.append(int(text))
    return out


def _replacement_reason_options():
    return list(
        ConfigOption.objects.filter(
            list_type='REPLACEMENT_REASON', module='DISPATCH', active=True
        ).order_by('sort_order', 'label')
    )


@login_required
def api_replace_technician(request, ticket_id):
    """
    POST /dispatch/api/tickets/<id>/replace-technician/

    Replaces the technician(s) currently on a ticket with new one(s).
    A replacement reason is MANDATORY, and when the chosen reason is "Other"
    a free-text note is mandatory too -- otherwise the reason is worthless.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(JobTicket, id=ticket_id)

    data = _parse_body(request)
    if data is None:
        return JsonResponse({'success': False, 'error': 'Malformed request body.'}, status=400)

    outgoing_ids = _get_ids(data, 'technician_ids')
    incoming_ids = _get_ids(data, 'replacement_technician_ids')
    reason_id = (data.get('replacement_reason_id') or '').strip()
    note = (data.get('replacement_note') or '').strip()

    if not incoming_ids:
        return JsonResponse({'success': False, 'error': 'Select at least one replacement technician.'}, status=400)

    if not outgoing_ids:
        outgoing_ids = list(
            ticket.tech_assignments.filter(is_current=True)
            .values_list('technician_id', flat=True)
        )
    if not outgoing_ids:
        outgoing_ids = list(ticket.technicians.values_list('id', flat=True))
    if not outgoing_ids:
        return JsonResponse({
            'success': False,
            'error': 'No technician is currently assigned to replace. Assign a technician first.'
        }, status=400)

    # ── The mandatory reason ─────────────────────────────────────────────
    if not reason_id:
        return JsonResponse({
            'success': False,
            'error': 'A replacement reason is required. Pick why this technician is being replaced.'
        }, status=400)

    reason = ConfigOption.objects.filter(
        id=reason_id, list_type='REPLACEMENT_REASON'
    ).first()
    if not reason:
        return JsonResponse({'success': False, 'error': 'Unknown replacement reason.'}, status=400)

    if OTHER_REASON_MARKER in reason.label.lower() and not note:
        return JsonResponse({
            'success': False,
            'error': 'You selected "Other". Describe the reason in the note field.'
        }, status=400)

    incoming = list(Technician.objects.filter(id__in=incoming_ids))
    if len(incoming) != len(set(incoming_ids)):
        return JsonResponse({'success': False, 'error': 'Duplicate technician selected.'}, status=400)

    # Don't let the same tech "replace" themselves -- that is a no-op that would
    # still consume a sequence number and pollute the handover history.
    if set(outgoing_ids) & {t.id for t in incoming}:
        return JsonResponse({
            'success': False,
            'error': 'A technician cannot replace themselves. Remove them from the current assignment first.'
        }, status=400)

    with transaction.atomic():
        outgoing_rows = list(
            ticket.tech_assignments.filter(is_current=True).select_for_update()
        )
        if not outgoing_rows:
            # Ticket predates handover tracking: synthesise rows so the
            # replacement still lands on an ordered history.
            max_seq = ticket.tech_assignments.aggregate(
                m=Max('sequence')
            )['m'] or 0
            for tech_id in outgoing_ids:
                TicketTechnicianAssignment.objects.create(
                    job_ticket=ticket, technician_id=tech_id,
                    sequence=max_seq + 1, is_current=True,
                )
            outgoing_rows = list(ticket.tech_assignments.filter(is_current=True))

        next_seq = ticket.tech_assignments.aggregate(
            m=Max('sequence')
        )['m'] or 0

        # Retire the outgoing tech(s): mark not-current, stamp the reason.
        for row in outgoing_rows:
            row.is_current = False
            row.replacement_reason = reason
            row.replacement_note = note or None
            row.replaced_by_user = request.user
            if not row.finished_at:
                row.finished_at = timezone.now()
            row.replaced_by = incoming[0]
            row.save(update_fields=[
                'is_current', 'replacement_reason', 'replacement_note',
                'replaced_by_user', 'finished_at', 'replaced_by',
            ])

        # Seat the replacement(s) as the current technician(s).
        for tech in incoming:
            next_seq += 1
            TicketTechnicianAssignment.objects.create(
                job_ticket=ticket,
                technician=tech,
                sequence=next_seq,
                is_current=True,
                assigned_at=timezone.now(),
            )

        # Keep the flat M2M in sync so every existing screen keeps working.
        ticket.technicians.set(incoming_ids)

        # A replaced technician is going back to the queue, not the field.
        if ticket.status == 'IN_PROGRESS':
            ticket.status = 'ASSIGNED'
            ticket.time_start = None
        ticket.save(update_fields=['status', 'time_start'])

        reason_label = reason.label + (f" - {note}" if note else "")
        outgoing_names = ', '.join(row.technician.name for row in outgoing_rows)
        incoming_names = ', '.join(t.name for t in incoming)

        JobTicketHistory.objects.create(
            job_ticket=ticket,
            actor=request.user,
            from_status='IN_PROGRESS',
            to_status='ASSIGNED',
            note=f"Technician replaced: {outgoing_names} -> {incoming_names}. Reason: {reason_label}",
        )
        log_audit(
            'UPDATE', 'JobTicket', ticket.id, request.user,
            summary=f"Replaced {outgoing_names} with {incoming_names}. Reason: {reason_label}",
        )

    return JsonResponse({
        'success': True,
        'ticket_number': ticket.ticket_number,
        'status': ticket.status,
        'current_technicians': incoming_names,
        'replacement_reason': reason.label,
        'replacement_note': note,
        'handover_chain': [
            {
                'sequence': a.sequence,
                'technician': a.technician.name,
                'is_current': a.is_current,
                'reason': a.reason_display,
            }
            for a in ticket.tech_assignments.select_related('technician', 'replacement_reason')
        ],
    })


@login_required
def api_ticket_replacement_reasons(request):
    """
    GET /dispatch/api/tickets/replacement-reasons/
    Feeds the replacement-reason dropdown on the dispatch ticket modal.
    """
    return JsonResponse({
        'success': True,
        'reasons': [
            {
                'id': r.id,
                'label': r.label,
                'requires_note': OTHER_REASON_MARKER in r.label.lower(),
            }
            for r in _replacement_reason_options()
        ],
    })