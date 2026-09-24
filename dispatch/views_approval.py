"""
Dispatch Pipeline Phase 4B: Quality Assurance, Admin Final Approval,
Bounce History, Admin Quality Summary, and Unreachable Client Close/Reopen Flows.
"""

import json
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from billing.models import Customer, Notification
from dispatch.models import CallAttemptLog, JobTicket, JobTicketHistory, TicketBounceHistory
from dispatch.views import log_audit

logger = logging.getLogger(__name__)


def is_admin_user(user):
    """Admin role check: Superuser, Admin role, or admin_approve permission."""
    return (
        user.is_superuser or
        getattr(user, 'role', '') == 'Admin' or
        user.has_perm('dispatch.admin_approve')
    )


def is_qa_user(user):
    """QA role check: Staff, Superuser, Dispatch, or dispatch_qa permission."""
    return (
        user.is_staff or
        user.is_superuser or
        getattr(user, 'role', '') in ['Admin', 'Staff', 'Dispatch'] or
        user.has_perm('dispatch.dispatch_qa')
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. DISPATCH QA REVIEW (Review time/date/problems, call client, pass/bounce)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def dispatch_qa(request):
    """
    Renders the QA Review cockpit for Dispatchers / Staff.
    """
    if not is_qa_user(request.user):
        messages.error(request, "Permission denied: QA review access required.")
        return redirect('dispatch_queue')

    tickets_awaiting_qa = JobTicket.objects.filter(
        status='COMPLETED'
    ).select_related('customer', 'team', 'qa_by').prefetch_related('technicians', 'bounces').order_by('-updated_at')

    recently_passed = JobTicket.objects.filter(
        status__in=['QA_PASSED', 'APPROVED']
    ).select_related('customer', 'team', 'qa_by').order_by('-updated_at')[:15]

    total_awaiting = tickets_awaiting_qa.count()
    repeated_bounces = JobTicket.objects.filter(status='COMPLETED', repeated_bounce_alert=True).count()
    same_person_alerts = JobTicket.objects.filter(status='COMPLETED', same_person_flag=True).count()

    return render(request, "dispatch/pipeline/4_qa.html", {
        "tickets": tickets_awaiting_qa,
        "qa_tickets": tickets_awaiting_qa,
        "recently_passed": recently_passed,
        "total_awaiting": total_awaiting,
        "repeated_bounces": repeated_bounces,
        "same_person_alerts": same_person_alerts,
    })


@login_required
def api_qa_review(request, ticket_id):
    """
    POST /dispatch/api/tickets/<ticket_id>/qa-review/
    Handles QA actions:
    - Pass to admin (or auto-complete for normal repairs)
    - Bounce to technician (type: 'revisit' with new timer OR 'correct_report')
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    if not is_qa_user(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied: QA authorization required.'}, status=403)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        action = data.get('action')

        if action == 'pass':
            client_called = data.get('client_called') or data.get('client_called_by_qa')
            if not client_called or client_called in ['false', 'False', 0, '0']:
                return JsonResponse({
                    'success': False,
                    'error': 'Confirmation that the client was called is required before passing QA.'
                }, status=400)

            qa_notes = (data.get('qa_notes') or '').strip()
            is_flagged = bool(data.get('is_flagged', False))

            ticket.client_called_by_qa = True
            ticket.qa_by = request.user
            ticket.qa_completed_at = timezone.now()
            ticket.qa_notes = qa_notes
            if is_flagged:
                ticket.is_flagged = True

            ticket.record_stage_action('QA_REVIEW', request.user)

            # RULE: Repairs skip admin approval unless bounced twice or flagged per SPEC
            needs_admin = (
                ticket.ticket_type != 'REPAIR' or
                ticket.bounce_count >= 2 or
                ticket.repeated_bounce_alert or
                ticket.is_flagged or
                ticket.same_person_flag
            )

            if needs_admin:
                old_status = ticket.status
                ticket.status = 'QA_PASSED'
                note = f"QA Passed by {request.user.username}. Forwarded to Admin Approval. Notes: {qa_notes}"
            else:
                old_status = ticket.status
                ticket.status = 'APPROVED'
                ticket.done_at = timezone.now()
                note = f"Repair QA Passed by {request.user.username}. Admin approval skipped per repair policy. Notes: {qa_notes}"
                if ticket.customer:
                    ticket.customer.installation_status = 'installed'
                    ticket.customer.save(update_fields=['installation_status'])

            ticket.save()
            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status=old_status,
                to_status=ticket.status,
                note=note,
            )
            log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=note)

            return JsonResponse({
                'success': True,
                'ticket_number': ticket.ticket_number,
                'status': ticket.status,
                'needs_admin': needs_admin,
                'message': note,
            })

        elif action == 'bounce':
            reason = (data.get('reason') or data.get('qa_notes') or '').strip()
            if not reason:
                return JsonResponse({'success': False, 'error': 'A mandatory reason is required to bounce the ticket.'}, status=400)

            bounce_type = data.get('bounce_type', 'correct_report')
            if bounce_type not in ['revisit', 'correct_report']:
                bounce_type = 'correct_report'

            ticket.bounce_count += 1
            if ticket.bounce_count >= 2:
                ticket.repeated_bounce_alert = True
                Notification.objects.create(
                    title=f"Repeated Bounce Alert: {ticket.ticket_number}",
                    message=f"Job for {ticket.client_name} bounced {ticket.bounce_count} times! Reason: {reason}",
                )

            old_status = ticket.status
            if bounce_type == 'revisit':
                ticket.status = 'ASSIGNED'
                # Reset timer for revisit
                ticket.time_start = None
                ticket.arrived_at = None
                ticket.time_accomplish = None
                ticket.finished_at = None
                ticket.duration = None
                ticket.done_duration = None
            else:
                ticket.status = 'IN_PROGRESS'

            ticket.record_stage_action('QA_BOUNCE', request.user)
            ticket.save()

            TicketBounceHistory.objects.create(
                ticket=ticket,
                from_stage='DISPATCH_QA',
                to_stage='TECHNICIAN',
                bounce_type=bounce_type,
                reason=reason,
                bounced_by=request.user,
            )

            bounce_note = f"QA Bounced to Technician ({bounce_type}): {reason}"
            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status=old_status,
                to_status=ticket.status,
                note=bounce_note,
            )
            log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=bounce_note)

            # Notification to technicians
            Notification.objects.create(
                title=f"Job Bounced: {ticket.ticket_number}",
                message=f"QA bounced job for {ticket.client_name} ({bounce_type}): {reason}",
            )

            return JsonResponse({
                'success': True,
                'ticket_number': ticket.ticket_number,
                'status': ticket.status,
                'bounce_count': ticket.bounce_count,
                'bounce_type': bounce_type,
                'message': bounce_note,
            })

        return JsonResponse({'success': False, 'error': f"Unknown action '{action}'"}, status=400)

    except Exception as e:
        logger.exception("Error in api_qa_review: %s", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════
# 2. ADMIN FINAL APPROVAL (Approve customer or bounce to dispatch QA)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def dispatch_approval(request):
    """
    Renders Admin Final Approval cockpit. Strictly restricted to Admins.
    """
    if not is_admin_user(request.user):
        messages.error(request, "Permission denied: Admin final approval required.")
        return redirect('dispatch_queue')

    pending_approval = JobTicket.objects.filter(
        status='QA_PASSED'
    ).select_related('customer', 'team', 'qa_by').prefetch_related('technicians', 'bounces').order_by('-updated_at')

    recently_approved = JobTicket.objects.filter(
        status='APPROVED'
    ).select_related('customer', 'team', 'admin_approved_by').order_by('-admin_approved_at')[:15]

    total_pending = pending_approval.count()
    repeated_bounces = JobTicket.objects.filter(status='QA_PASSED', repeated_bounce_alert=True).count()
    same_person_alerts = JobTicket.objects.filter(status='QA_PASSED', same_person_flag=True).count()

    return render(request, "dispatch/pipeline/5_approval.html", {
        "tickets": pending_approval,
        "recently_approved": recently_approved,
        "total_pending": total_pending,
        "repeated_bounces": repeated_bounces,
        "same_person_alerts": same_person_alerts,
    })


@login_required
def api_admin_approve(request, ticket_id):
    """
    POST /dispatch/api/tickets/<ticket_id>/admin-approve/
    Handles Admin Sign-Off:
    - Approve: activates customer, marks ticket APPROVED
    - Bounce to Dispatch: returns ticket to COMPLETED (QA) with mandatory reason
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    if not is_admin_user(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied: Admin authorization required.'}, status=403)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        action = data.get('action')

        if action == 'approve':
            old_status = ticket.status
            ticket.status = 'APPROVED'
            ticket.admin_approved_at = timezone.now()
            ticket.admin_approved_by = request.user
            ticket.done_at = timezone.now()
            ticket.record_stage_action('ADMIN_APPROVED', request.user)
            ticket.save()

            customer = ticket.customer
            if customer:
                customer.status = 'active'
                customer.installation_status = 'installed'
                customer.installed_at = timezone.now()
                if customer.agent:
                    customer.agent_lock_until = timezone.now() + timezone.timedelta(days=60)
                customer.save()

            note = f"Admin Final Approval granted by {request.user.username}. Customer activated."
            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status=old_status,
                to_status='APPROVED',
                note=note,
            )
            log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=note)

            Notification.objects.create(
                title=f"Customer Activated: {ticket.client_name}",
                message=f"Job Order {ticket.ticket_number} approved by Admin {request.user.username}. Subscriber line is now Active.",
            )

            return JsonResponse({
                'success': True,
                'ticket_number': ticket.ticket_number,
                'status': 'APPROVED',
                'message': note,
            })

        elif action == 'bounce':
            reason = (data.get('reason') or data.get('admin_notes') or '').strip()
            if not reason:
                return JsonResponse({'success': False, 'error': 'A mandatory reason is required to bounce back to Dispatch.'}, status=400)

            ticket.bounce_count += 1
            if ticket.bounce_count >= 2:
                ticket.repeated_bounce_alert = True
                Notification.objects.create(
                    title=f"Repeated Bounce Alert: {ticket.ticket_number}",
                    message=f"Admin bounced ticket {ticket.ticket_number} (Bounce count: {ticket.bounce_count})! Reason: {reason}",
                )

            old_status = ticket.status
            ticket.status = 'COMPLETED'  # Return to Dispatch QA
            ticket.record_stage_action('ADMIN_BOUNCE', request.user)
            ticket.save()

            TicketBounceHistory.objects.create(
                ticket=ticket,
                from_stage='ADMIN_APPROVAL',
                to_stage='DISPATCH_QA',
                bounce_type='admin_to_dispatch',
                reason=reason,
                bounced_by=request.user,
            )

            bounce_note = f"Admin Bounced to Dispatch QA: {reason}"
            JobTicketHistory.objects.create(
                job_ticket=ticket,
                actor=request.user,
                from_status=old_status,
                to_status='COMPLETED',
                note=bounce_note,
            )
            log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=bounce_note)

            Notification.objects.create(
                title=f"Admin Bounced Ticket: {ticket.ticket_number}",
                message=f"Admin {request.user.username} returned ticket for {ticket.client_name} to Dispatch QA: {reason}",
            )

            return JsonResponse({
                'success': True,
                'ticket_number': ticket.ticket_number,
                'status': 'COMPLETED',
                'bounce_count': ticket.bounce_count,
                'message': bounce_note,
            })

        return JsonResponse({'success': False, 'error': f"Unknown action '{action}'"}, status=400)

    except Exception as e:
        logger.exception("Error in api_admin_approve: %s", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════
# 3. ADMIN QUALITY SUMMARY & PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def dispatch_admin_summary(request):
    """
    Renders Quality Assurance & Bounce Patterns summary for Administrators.
    Shows patterns by user, stage, reason, same-person audit flags,
    and displays unreachable returns strictly separately from quality bounces.
    """
    if not (is_admin_user(request.user) or request.user.has_perm('dispatch.view_bounce_summary')):
        messages.error(request, "Permission denied: Admin summary access required.")
        return redirect('dispatch_queue')

    total_bounces = TicketBounceHistory.objects.count()
    repeated_bounces_count = JobTicket.objects.filter(repeated_bounce_alert=True).count()
    same_person_count = JobTicket.objects.filter(same_person_flag=True).count()
    unreachable_count = JobTicket.objects.filter(
        status='CANCELLED',
        cancellation_reason__in=['no_contact', 'change_of_mind', 'undecided', 'other']
    ).count()

    # Patterns by User (who triggered bounces)
    user_patterns = TicketBounceHistory.objects.values(
        'bounced_by__id', 'bounced_by__username', 'bounced_by__first_name', 'bounced_by__last_name'
    ).annotate(count=Count('id')).order_by('-count')[:10]

    # Patterns by Stage (from_stage -> to_stage)
    stage_patterns = TicketBounceHistory.objects.values(
        'from_stage', 'to_stage'
    ).annotate(count=Count('id')).order_by('-count')

    # Patterns by Reason / Type
    type_patterns = TicketBounceHistory.objects.values(
        'bounce_type'
    ).annotate(count=Count('id')).order_by('-count')

    # Recent Bounce History
    recent_bounces = TicketBounceHistory.objects.select_related(
        'ticket', 'bounced_by'
    ).order_by('-created_at')[:25]

    # Same-person flag jobs (1 person executed 2+ stages)
    same_person_tickets = JobTicket.objects.filter(
        same_person_flag=True
    ).select_related('customer', 'team').order_by('-updated_at')[:30]

    # Unreachable Returns (Tracked separately per Spec #12 & #17)
    unreachable_tickets = JobTicket.objects.filter(
        status='CANCELLED'
    ).exclude(
        cancellation_reason__isnull=True
    ).exclude(
        cancellation_reason=''
    ).select_related('customer', 'team').prefetch_related('technicians').order_by('-updated_at')[:30]

    return render(request, "dispatch/admin_summary.html", {
        "total_bounces": total_bounces,
        "repeated_bounces_count": repeated_bounces_count,
        "same_person_count": same_person_count,
        "unreachable_count": unreachable_count,
        "user_patterns": user_patterns,
        "stage_patterns": stage_patterns,
        "type_patterns": type_patterns,
        "recent_bounces": recent_bounces,
        "same_person_tickets": same_person_tickets,
        "unreachable_tickets": unreachable_tickets,
    })


# ═══════════════════════════════════════════════════════════════════════════
# 4. UNREACHABLE CLIENT CLOSE FLOW & REOPEN ONBOARDING
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def api_close_unreachable(request, ticket_id):
    """
    POST /dispatch/api/tickets/<ticket_id>/close-unreachable/
    Dispatch closes an unreachable customer:
    - Reasons: 'no_contact', 'change_of_mind', 'undecided', 'other'
    - Mandatory checkbox: client and agent informed
    - Customer marked 'closed_not_installed' (excluded from lists/incentives)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    if not is_qa_user(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    ticket = get_object_or_404(JobTicket, id=ticket_id)
    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        reason = data.get('reason') or data.get('close_reason') or 'no_contact'
        notes = (data.get('notes') or '').strip()
        client_agent_informed = data.get('client_agent_informed')

        if not client_agent_informed or client_agent_informed in ['false', 'False', 0, '0']:
            return JsonResponse({
                'success': False,
                'error': 'Confirmation that both client and agent were informed is required.'
            }, status=400)

        old_status = ticket.status
        ticket.status = 'CANCELLED'
        ticket.cancellation_reason = reason
        ticket.close_reason = 'Unreachable' if reason == 'no_contact' else reason.replace('_', ' ').title()
        ticket.close_reason_note = notes
        ticket.client_agent_informed = True
        ticket.record_stage_action('CLOSED_UNREACHABLE', request.user)
        ticket.save()

        if ticket.customer:
            ticket.customer.installation_status = 'closed_not_installed'
            ticket.customer.save(update_fields=['installation_status'])

        note = f"Job Order closed by Dispatch. Reason: {ticket.close_reason}. Agent informed. {notes}"
        JobTicketHistory.objects.create(
            job_ticket=ticket,
            actor=request.user,
            from_status=old_status,
            to_status='CANCELLED',
            note=note,
        )
        log_audit('UPDATE', 'JobTicket', ticket.id, request.user, summary=note)

        return JsonResponse({
            'success': True,
            'ticket_number': ticket.ticket_number,
            'status': 'CANCELLED',
            'message': note,
        })

    except Exception as e:
        logger.exception("Error in api_close_unreachable: %s", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def api_reopen_onboarding(request, customer_id):
    """
    POST /dispatch/api/customers/<customer_id>/reopen-onboarding/
    When an unreachable client returns:
    - Reuse the existing customer record
    - Customer installation_status set back to 'pending_installation'
    - Generates new job order and redirects to checklist
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    customer = get_object_or_404(Customer, id=customer_id)
    try:
        customer.installation_status = 'pending_installation'
        customer.save(update_fields=['installation_status'])

        log_audit('UPDATE', 'Customer', customer.id, request.user, summary="Reopened onboarding for previously unreachable customer.")

        return JsonResponse({
            'success': True,
            'customer_id': customer.id,
            'redirect_url': f'/checklist/?customer_id={customer.id}&reopened=1',
            'message': f"Customer {customer.full_name} reopened for onboarding. Please execute the checklist.",
        })

    except Exception as e:
        logger.exception("Error in api_reopen_onboarding: %s", e)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
