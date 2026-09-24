from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
from billing.models import Prospect, ChecklistConfirmation, Agent, Barangay, SubscriptionPlan, SystemLog
from billing.decorators import has_dispatch_permission


@login_required
def prospects_inbox(request):
    """
    Staff Prospect Inbox:
    Allows Dispatch and Staff to view, filter, review, and act on agent-submitted referral prospects.
    Agents are strictly forbidden from viewing this staff view.
    """
    if hasattr(request.user, "agent_profile") and not request.user.is_staff:
        messages.error(request, "Access restricted: Agents cannot view the staff prospect inbox.")
        return redirect("agent_dashboard")

    # Filter parameters
    status_filter = request.GET.get("status", "all").strip().lower()
    duplicate_filter = request.GET.get("duplicate", "").strip().lower()
    agent_id = request.GET.get("agent_id", "").strip()
    search_q = request.GET.get("q", "").strip()

    qs = Prospect.objects.select_related("agent", "barangay", "plan", "submitted_by", "opened_by_staff_user").all()

    if status_filter and status_filter != "all":
        qs = qs.filter(status=status_filter)

    if duplicate_filter == "1" or duplicate_filter == "true":
        qs = qs.filter(duplicate_flag=True)

    if agent_id:
        qs = qs.filter(agent_id=agent_id)

    if search_q:
        qs = qs.filter(
            Q(full_name__icontains=search_q)
            | Q(phone__icontains=search_q)
            | Q(address__icontains=search_q)
            | Q(barangay__name__icontains=search_q)
        )

    # Status counts for tab pills
    base_qs = Prospect.objects.all()
    counts = {
        "all": base_qs.count(),
        "submitted": base_qs.filter(status="submitted").count(),
        "under_review": base_qs.filter(status="under_review").count(),
        "converted": base_qs.filter(status="converted").count(),
        "declined": base_qs.filter(status="declined").count(),
        "duplicates": base_qs.filter(duplicate_flag=True).count(),
    }

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "prospects": page_obj,
        "counts": counts,
        "current_status": status_filter,
        "duplicate_filter": duplicate_filter,
        "agents": Agent.objects.all(),
        "selected_agent": agent_id,
        "search_q": search_q,
    }
    return render(request, "billing/prospects/inbox.html", context)


@login_required
def prospect_detail(request, prospect_id):
    """
    Staff review view for a single prospect.
    Sets opened_by_staff_at & opened_by_staff_user to lock out agent edits,
    displays duplicate warnings, and provides CTAs to run checklist or decline.
    """
    if hasattr(request.user, "agent_profile") and not request.user.is_staff:
        messages.error(request, "Access restricted: Agents cannot view the staff prospect details.")
        return redirect("agent_dashboard")

    prospect = get_object_or_404(Prospect.objects.select_related("agent", "barangay", "plan", "duplicate_of", "converted_customer"), id=prospect_id)

    # Lock agent editing when staff reviews the prospect
    if not prospect.opened_by_staff_at:
        prospect.opened_by_staff_at = timezone.now()
        prospect.opened_by_staff_user = request.user
        if prospect.status == "submitted":
            prospect.status = "under_review"
        prospect.save(update_fields=["opened_by_staff_at", "opened_by_staff_user", "status"])

    # Look up potential matching customers/prospects for duplicate warnings
    matching_customers = []
    if prospect.phone:
        from billing.models import Customer
        matching_customers = Customer.objects.filter(
            Q(phone=prospect.phone) | Q(full_name__iexact=prospect.full_name)
        ).exclude(id=prospect.converted_customer_id if prospect.converted_customer else -1)[:5]

    context = {
        "prospect": prospect,
        "matching_customers": matching_customers,
    }
    return render(request, "billing/prospects/detail.html", context)


@login_required
def prospect_decline(request, prospect_id):
    """
    Declines an agent-submitted referral.
    Records ChecklistConfirmation with outcome='declined' and updates prospect status to 'declined'.
    Creates NO customer.
    """
    if hasattr(request.user, "agent_profile") and not request.user.is_staff:
        messages.error(request, "Access restricted.")
        return redirect("agent_dashboard")

    prospect = get_object_or_404(Prospect, id=prospect_id)

    if request.method == "POST":
        decline_reason = request.POST.get("decline_reason", "").strip()
        method = request.POST.get("method", "phone").strip()

        if not decline_reason:
            messages.error(request, "A decline reason is mandatory.")
            return redirect("prospect_detail", prospect_id=prospect.id)

        prospect.status = "declined"
        prospect.decline_reason = decline_reason
        prospect.save(update_fields=["status", "decline_reason", "updated_at"])

        ChecklistConfirmation.objects.create(
            prospect=prospect,
            confirmed_by=request.user,
            method=method,
            outcome="declined",
            decline_reason=decline_reason,
            applicant_name=prospect.full_name,
            applicant_phone=prospect.phone,
            notes=f"Declined by staff {request.user.username} via prospect review.",
        )

        try:
            SystemLog.objects.create(
                table_name="Prospect",
                record_id=str(prospect.id),
                action="DECLINE",
                changed_by=request.user.username,
                target_name=prospect.full_name,
                old_data="status=submitted/under_review",
                new_data=f"status=declined\nreason={decline_reason}",
            )
        except Exception:
            pass

        messages.info(request, f"Referral application for {prospect.full_name} has been marked as declined. No customer created.")
        return redirect("prospects_inbox")

    return redirect("prospect_detail", prospect_id=prospect.id)
