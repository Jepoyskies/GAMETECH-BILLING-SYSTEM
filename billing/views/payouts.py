import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from billing.decorators import has_dispatch_permission
from billing.models import Agent, AgentPayoutBatch, IncentiveSetting
from billing.services.incentives import (
    get_agent_incentive_summary,
    create_agent_payout_batch,
    mark_agent_payout_batch_paid,
)

logger = logging.getLogger(__name__)


def _can_manage_payouts(user):
    """Checks if the user has permission to manage agent payouts."""
    if not user or not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.has_perm("billing.mark_payout_paid")
        or has_dispatch_permission(user, "mark_payout_paid")
    )


@login_required
def agent_payouts_list(request):
    """
    Admin Payout Dashboard:
    - Lists agents with >= 5 unpaid qualified customers ready for cashout
    - Displays pending payout batches awaiting payment approval
    - Displays permanent payout history ledger
    - Gated strictly by 'billing.mark_payout_paid' permission.
    """
    if not _can_manage_payouts(request.user):
        messages.error(request, "Permission denied: You do not have permission to view or manage agent payouts.")
        return redirect("agent_list")

    settings_obj = IncentiveSetting.get_settings()
    agents = Agent.objects.all().order_by("name")

    ready_agents = []
    progressing_agents = []
    other_agents = []

    total_claimable_ready = Decimal("0.00")
    total_unpaid_qualified = 0

    for agent in agents:
        summary = get_agent_incentive_summary(agent)
        agent_data = {
            "agent": agent,
            "summary": summary,
            "eligible_sizes": [
                s
                for s in range(
                    settings_obj.batch_size,
                    summary["unpaid_qualified"] + 1,
                    settings_obj.batch_size,
                )
            ]
            if summary["unpaid_qualified"] >= settings_obj.batch_size
            else [],
        }

        total_unpaid_qualified += summary["unpaid_qualified"]

        if summary["unpaid_qualified"] >= settings_obj.batch_size:
            ready_agents.append(agent_data)
            total_claimable_ready += summary["claimable_amount"]
        elif summary["unpaid_qualified"] > 0:
            progressing_agents.append(agent_data)
        else:
            other_agents.append(agent_data)

    pending_batches = (
        AgentPayoutBatch.objects.filter(status="pending")
        .select_related("agent", "paid_by")
        .prefetch_related("customers")
        .order_by("-created_at")
    )
    total_pending_amount = (
        pending_batches.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    )

    completed_batches = (
        AgentPayoutBatch.objects.filter(status="paid")
        .select_related("agent", "paid_by")
        .prefetch_related("customers")
        .order_by("-paid_at", "-created_at")
    )
    total_paid_out = (
        completed_batches.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    )

    context = {
        "settings": settings_obj,
        "ready_agents": ready_agents,
        "progressing_agents": progressing_agents,
        "other_agents": other_agents,
        "pending_batches": pending_batches,
        "completed_batches": completed_batches,
        "total_claimable_ready": total_claimable_ready,
        "total_pending_amount": total_pending_amount,
        "total_paid_out": total_paid_out,
        "total_unpaid_qualified": total_unpaid_qualified,
    }
    return render(request, "billing/payouts/index.html", context)


@login_required
def create_payout_batch_view(request, agent_id):
    """
    Creates a payout batch for an agent in multiples of 5 (oldest qualified first).
    """
    if not _can_manage_payouts(request.user):
        messages.error(request, "Permission denied: You do not have permission to create payout batches.")
        return redirect("agent_payouts_list")

    if request.method != "POST":
        return redirect("agent_payouts_list")

    agent = get_object_or_404(Agent, id=agent_id)
    batch_size = request.POST.get("batch_size")
    notes = request.POST.get("notes", "").strip()

    try:
        batch = create_agent_payout_batch(
            agent=agent,
            batch_size_to_create=batch_size,
            user=request.user,
            notes=notes,
        )
        messages.success(
            request,
            f"Payout Batch {batch.batch_number} created successfully for {agent.name}! "
            f"Amount: ₱{batch.amount:,.2f} ({batch.customer_count} subscribers). "
            f"Batch is pending payment confirmation.",
        )
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.error(f"Failed to create payout batch for agent {agent_id}: {e}", exc_info=True)
        messages.error(request, f"Error creating payout batch: {e}")

    return redirect("agent_payouts_list")


@login_required
def mark_payout_batch_paid_view(request, batch_id):
    """
    Marks a pending payout batch as PAID with reference number and records paid_by/paid_at.
    """
    if not _can_manage_payouts(request.user):
        messages.error(request, "Permission denied: You do not have permission to mark payout batches as paid.")
        return redirect("agent_payouts_list")

    if request.method != "POST":
        return redirect("agent_payouts_list")

    batch = get_object_or_404(AgentPayoutBatch, id=batch_id)
    reference_no = request.POST.get("reference_no", "").strip()
    notes = request.POST.get("notes", "").strip()

    try:
        mark_agent_payout_batch_paid(
            batch=batch,
            user=request.user,
            reference_no=reference_no,
            notes=notes,
        )
        messages.success(
            request,
            f"Payout Batch {batch.batch_number} for {batch.agent.name} (₱{batch.amount:,.2f}) has been marked as PAID! "
            f"Reference: {reference_no or 'N/A'}.",
        )
    except Exception as e:
        logger.error(f"Failed to mark payout batch {batch_id} as paid: {e}", exc_info=True)
        messages.error(request, f"Error marking payout batch as paid: {e}")

    return redirect("agent_payouts_list")
