"""
Agent portal context -- the single source for what an agent's dashboard shows.

Why this is a service and not a view
------------------------------------
`agent_dashboard` (the agent logging in) and `staff_agent_portal_detail` (a CSR
opening the agent to check on him) each carried their own byte-identical copy of
this logic. They drifted, which is why clicking "View" on an agent showed a page
that looked nothing like the portal the agent actually uses.

One builder, one template. What staff inspect is literally what the agent sees.

Two rules this module must not break:
  * Strict isolation -- everything is scoped to ONE agent's own records.
  * Rule 35 -- installation (hardware), dispatch (is a tech coming) and billing
    (paid / expiry) are three independent facts. Report them side by side; never
    infer one from another.
"""
from decimal import Decimal

from django.utils import timezone

from billing.models import (
    AgentPayoutBatch,
    AgentQualificationEvent,
    Barangay,
    Customer,
    Payment,
    Prospect,
)
from billing.services.incentives import (
    get_agent_incentive_summary,
    get_customer_qualifying_paid_total,
)


def agent_customer_tracking(agent):
    """The four things a sales agent is asked after handing a customer over:

      1. Is the line installed yet, or still waiting for a technician?
      2. Has a technician been scheduled, and are they on the way?
      3. Has this customer paid?
      4. When does it expire, so I renew before they complain?

    A customer can be installed but unpaid, or paid with an open repair ticket.
    Both facts are reported, neither is derived from the other.
    """
    from dispatch.models import JobTicket

    OPEN_TICKETS = ("PENDING", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "QA_PASSED")
    now = timezone.now()

    customers = list(
        Customer.objects.filter(agent=agent)
        .select_related("plan")
        .order_by("-created_at")
    )
    if not customers:
        return []

    # One query for the money rather than two per customer.
    paid_by_customer = {}
    for username, amount, when in Payment.objects.filter(
        username__in=[c.pppoe_username for c in customers if c.pppoe_username]
    ).values_list("username", "amount", "created_at"):
        agg = paid_by_customer.setdefault(
            username,
            {"total": Decimal("0.00"), "last": None, "last_amount": None},
        )
        agg["total"] += Decimal(amount or 0)
        if agg["last"] is None or (when and when > agg["last"]):
            agg["last"] = when
            agg["last_amount"] = Decimal(amount or 0)

    # The latest still-open ticket is the one the agent cares about ("is a tech
    # coming?"). Closed tickets are history, not news.
    tickets_by_customer = {}
    for t in (
        JobTicket.objects.filter(customer__in=customers, status__in=OPEN_TICKETS)
        .select_related("customer")
        .prefetch_related("technicians")
        .order_by("-created_at")
    ):
        tickets_by_customer.setdefault(t.customer_id, t)

    rows = []
    for c in customers:
        money = paid_by_customer.get(c.pppoe_username)
        ticket = tickets_by_customer.get(c.id)

        rows.append({
            "customer": c,
            "name": c.full_name,
            "pppoe_username": c.pppoe_username,
            "plan": c.plan.name if c.plan else None,
            "installation_status": c.get_installation_status_display(),
            "is_installed": c.installation_status == "installed",
            "expires_at": c.expires_at,
            "days_left": (c.expires_at - now).days if c.expires_at else None,
            "no_expiry": c.expires_at is None,
            "total_paid": money["total"] if money else Decimal("0.00"),
            "last_paid_at": money["last"] if money else None,
            "last_paid_amount": money["last_amount"] if money else None,
            "has_paid": bool(money and money["total"] > 0),
            "balance": c.outstanding_balance,
            "ticket": ticket,
            "ticket_status": ticket.get_status_display() if ticket else None,
            "ticket_number": ticket.ticket_number if ticket else None,
            "ticket_scheduled": (
                # scheduled_time is nullable; concatenating None printed the
                # literal string "None" next to the date.
                " ".join(
                    str(p) for p in (ticket.scheduled_date,
                                     ticket.scheduled_time) if p
                ).strip()
                if ticket and ticket.scheduled_date else None
            ),
            "technicians": (
                ", ".join(t.name for t in ticket.technicians.all())
                if ticket else ""
            ),
        })
    return rows


def _decorate_prospects(prospects, agent):
    """Attach qualification state and 2nd-month progress text to each referral."""
    for p in prospects:
        cust = p.converted_customer
        if not cust:
            p.qualification_status = "prospect"
            p.progress_text = "Pending Onboarding"
            p.unlock_date = None
            continue

        event = AgentQualificationEvent.objects.filter(
            customer=cust, agent=agent
        ).first()

        if event and event.status == "paid_out":
            p.qualification_status = "paid_out"
            p.progress_text = "Paid Out (₱500)"
            p.is_qualified = True
        elif event and event.status == "qualified":
            p.qualification_status = "qualified"
            p.progress_text = "Qualified (₱500)"
            p.is_qualified = True
        elif event and event.status == "revoked":
            p.qualification_status = "revoked"
            p.progress_text = "Revoked (Rollback)"
            p.is_qualified = False
        else:
            cancelled = (
                cust.status in ["closed_not_installed", "pull out"]
                or cust.installation_status == "closed_not_installed"
            )
            if cancelled:
                p.qualification_status = "cancelled"
                p.progress_text = "Cancelled (Ineligible)"
                p.is_qualified = False
            else:
                net_paid = get_customer_qualifying_paid_total(cust)
                plan_price = (
                    cust.plan.price if cust.plan and cust.plan.price
                    else Decimal("0.00")
                )
                threshold = Decimal("2.00") * plan_price

                if plan_price <= 0:
                    p.qualification_status = "pending_payment"
                    p.progress_text = "No plan price set"
                    p.is_qualified = False
                elif net_paid >= threshold:
                    p.qualification_status = "qualified"
                    p.progress_text = "Qualified (₱500)"
                    p.is_qualified = True
                elif net_paid > plan_price:
                    p.qualification_status = "in_progress"
                    p.progress_text = (
                        f"PHP {net_paid - plan_price:,.0f} paid, "
                        f"PHP {threshold - net_paid:,.0f} remaining"
                    )
                    p.is_qualified = False
                elif net_paid > 0:
                    p.qualification_status = "in_progress"
                    p.progress_text = f"PHP 0 paid, PHP {plan_price:,.0f} remaining"
                    p.is_qualified = False
                else:
                    p.qualification_status = "pending_payment"
                    p.progress_text = "Pending 1st Payment"
                    p.is_qualified = False

        p.unlock_date = cust.agent_lock_until
    return prospects


def agent_portal_context(agent):
    """Everything the agent portal dashboard renders, for ONE agent."""
    prospects = _decorate_prospects(
        Prospect.objects.filter(agent=agent)
        .select_related(
            "barangay", "plan", "converted_customer", "converted_customer__plan"
        )
        .order_by("-created_at"),
        agent,
    )

    summary = get_agent_incentive_summary(agent)
    batch_size = summary["batch_size"]
    progress_count = summary["progress_to_next"]

    return {
        "agent": agent,
        "prospects": prospects,
        "claimable_commission": summary["claimable_amount"],
        "unpaid_qualified": summary["unpaid_qualified"],
        "total_qualified": summary["total_qualified"],
        "batch_size": batch_size,
        "progress_count": progress_count,
        "progress_pct": (
            min(100, int((progress_count / batch_size) * 100))
            if batch_size else 0
        ),
        "is_cashout_eligible": summary["is_cashout_eligible"],
        "payout_history": AgentPayoutBatch.objects.filter(agent=agent)
        .order_by("-created_at"),
        "barangays": Barangay.objects.all(),
        # The four questions an agent actually asks about their own customers.
        "tracked_customers": agent_customer_tracking(agent),
    }
