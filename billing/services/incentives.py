import logging
import re
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from billing.models import (
    Customer,
    Agent,
    Payment,
    AgentQualificationEvent,
    AgentPayoutBatch,
    IncentiveSetting,
    SystemLog,
)

logger = logging.getLogger(__name__)


def get_customer_qualifying_paid_total(customer):
    """
    Sums net qualifying subscription payments for a customer:
    - Sums all Payment amounts (positive payments add, negative rollback payments subtract)
    - Excludes non-internet/add-on services (e.g. Cignal Subscription)
    - Excludes one-time fees (such as ₱500 GIMI upgrade fee found in Payment.reason)
    """
    if not customer:
        return Decimal("0.00")

    payments = Payment.objects.filter(customer=customer).exclude(
        plan_name__iexact="Cignal Subscription"
    )
    total = Decimal("0.00")
    for p in payments:
        amt = Decimal(str(p.amount or 0))
        if p.reason:
            reason_lower = p.reason.lower()
            if "upgrade fee" in reason_lower or "one-time upgrade fee" in reason_lower:
                # Look for an explicit amount if present, else default to 500.00
                fee_match = re.search(r"(\d+(?:\.\d{2})?)\s*(?:one-time upgrade fee|upgrade fee)", reason_lower)
                fee = Decimal(fee_match.group(1)) if fee_match else Decimal("500.00")
                amt -= fee
        total += amt
    return max(Decimal("0.00"), total)


def evaluate_agent_qualification(customer, triggering_payment=None):
    """
    Evaluates whether an agent-referred customer has qualified for the incentive
    (2nd month paid: later payment, 2+ month advance, or cumulative partials reaching 2x plan price).

    Rules (SPEC Decision 7):
    - Agent-referred customers created through the new flow.
    - Legacy, router-sync, and non-agent customers never count.
    - Cancelled before qualifying never count ('closed_not_installed', 'pull out').
    - Already-qualified stay counted even if later disconnected.
    - If qualifying payment is rolled back before payout, revoke and flag it.
    - Idempotent: re-saving or re-processing never creates duplicate events.
    """
    if not customer:
        return None

    # 1. Non-agent check
    agent = customer.original_agent or customer.agent
    if not agent:
        return None

    # 2. Legacy / router-sync exclusion
    if customer.source in ["router_sync", "legacy", "recovery"]:
        return None

    # Check existing qualification event for this customer and agent
    existing_event = AgentQualificationEvent.objects.filter(
        customer=customer, agent=agent
    ).first()

    # Calculate net qualifying payment total
    net_paid = get_customer_qualifying_paid_total(customer)

    # Threshold is 2x the customer's monthly plan price
    plan_price = customer.plan.price if customer.plan and customer.plan.price else Decimal("0.00")
    if plan_price <= Decimal("0.00"):
        return None

    threshold = Decimal("2.00") * plan_price

    # 3. Already-qualified handling & Rollback revocation check
    if existing_event:
        if existing_event.status == "paid_out":
            # Already paid out in a completed payout batch. Permanent record.
            return existing_event

        if existing_event.status == "qualified":
            # Check if rollback caused net paid to fall below the 2-month threshold
            if net_paid < threshold:
                existing_event.status = "revoked"
                existing_event.revocation_reason = (
                    f"Qualifying payment rolled back or adjusted. "
                    f"Net paid (₱{net_paid:,.2f}) dropped below the 2-month threshold of ₱{threshold:,.2f}."
                )
                existing_event.save(update_fields=["status", "revocation_reason"])

                try:
                    SystemLog.objects.create(
                        table_name="AgentQualificationEvent",
                        record_id=str(existing_event.id),
                        action="REVOKE_INCENTIVE",
                        changed_by="system",
                        target_name=customer.full_name,
                        old_data="status=qualified",
                        new_data=f"status=revoked\nreason={existing_event.revocation_reason}",
                    )
                except Exception:
                    pass
                return existing_event

            # Still qualified and >= threshold; idempotent return
            return existing_event

    # 4. If customer cancelled before qualifying, they never count
    is_cancelled = (
        customer.status in ["closed_not_installed", "pull out"]
        or customer.installation_status == "closed_not_installed"
    )
    if is_cancelled:
        return None

    # 5. Check if net paid meets or exceeds 2x monthly plan price
    if net_paid >= threshold:
        settings_obj = IncentiveSetting.get_settings()
        incentive_amount = settings_obj.incentive_amount

        # Find triggering payment if not provided
        if not triggering_payment:
            triggering_payment = (
                Payment.objects.filter(customer=customer)
                .exclude(payment_method="Rollback")
                .order_by("-paid_at", "-id")
                .first()
            )

        with transaction.atomic():
            if existing_event and existing_event.status == "revoked":
                # Customer re-qualified after a previous rollback
                existing_event.status = "qualified"
                existing_event.revocation_reason = None
                existing_event.payment = triggering_payment
                existing_event.qualifying_amount = incentive_amount
                existing_event.save()
                event = existing_event
            else:
                event = AgentQualificationEvent.objects.create(
                    customer=customer,
                    agent=agent,
                    payment=triggering_payment,
                    qualifying_amount=incentive_amount,
                    status="qualified",
                    is_test_data=customer.is_test_data,
                )

            # Auto-stamp first_payment_date and agent_lock_until if not already set
            fields_to_update = []
            if not customer.first_payment_date:
                first_pay = (
                    Payment.objects.filter(customer=customer, amount__gt=0)
                    .order_by("paid_at", "id")
                    .first()
                )
                if first_pay and first_pay.paid_at:
                    customer.first_payment_date = first_pay.paid_at.date()
                else:
                    customer.first_payment_date = timezone.now().date()
                fields_to_update.append("first_payment_date")

            if not customer.agent_lock_until:
                customer.agent_lock_until = timezone.now() + timezone.timedelta(days=settings_obj.lock_days)
                fields_to_update.append("agent_lock_until")

            if fields_to_update:
                customer.save(update_fields=fields_to_update)

            try:
                SystemLog.objects.create(
                    table_name="AgentQualificationEvent",
                    record_id=str(event.id),
                    action="QUALIFY_INCENTIVE",
                    changed_by="system",
                    target_name=customer.full_name,
                    old_data="",
                    new_data=f"Agent: {agent.name}\nCustomer: {customer.full_name}\nAmount: ₱{incentive_amount}\nNet Paid: ₱{net_paid:,.2f}",
                )
            except Exception:
                pass

            return event

    return None


def get_agent_incentive_summary(agent):
    """
    Calculates the live incentive status for an agent from the ledger:
    - total_qualified: all events with status in ['qualified', 'paid_out']
    - unpaid_qualified: events with status == 'qualified' and payout_batch__isnull=True
    - eligible_batch_count: unpaid_qualified // batch_size
    - claimable_amount: eligible_batch_count * (batch_size * incentive_amount)
    - carry_over_count: unpaid_qualified % batch_size
    - progress_to_next_5: unpaid_qualified % batch_size
    """
    settings_obj = IncentiveSetting.get_settings()
    batch_size = settings_obj.batch_size
    incentive_amount = settings_obj.incentive_amount

    all_events = AgentQualificationEvent.objects.filter(agent=agent)
    total_qualified = all_events.filter(status__in=["qualified", "paid_out"]).count()
    unpaid_events = all_events.filter(status="qualified", payout_batch__isnull=True)
    unpaid_count = unpaid_events.count()

    eligible_batches = unpaid_count // batch_size if batch_size > 0 else 0
    claimable_amount = Decimal(str(eligible_batches * batch_size)) * incentive_amount
    carry_over = unpaid_count % batch_size if batch_size > 0 else 0

    return {
        "batch_size": batch_size,
        "incentive_amount": incentive_amount,
        "batch_payout_amount": Decimal(str(batch_size)) * incentive_amount,
        "total_qualified": total_qualified,
        "unpaid_qualified": unpaid_count,
        "eligible_batches": eligible_batches,
        "claimable_amount": claimable_amount,
        "carry_over": carry_over,
        "progress_to_next": carry_over,
        "is_cashout_eligible": unpaid_count >= batch_size,
    }


def create_agent_payout_batch(agent, batch_size_to_create=None, user=None, notes=""):
    """
    Creates an AgentPayoutBatch for an agent.
    batch_size_to_create must be a multiple of IncentiveSetting.batch_size (e.g. 5, 10, 15).
    Selects the OLDEST qualified events (FIFO) and attaches them to the batch.
    """
    settings_obj = IncentiveSetting.get_settings()
    std_batch_size = settings_obj.batch_size
    incentive_amount = settings_obj.incentive_amount

    unpaid_events_qs = (
        AgentQualificationEvent.objects.filter(
            agent=agent, status="qualified", payout_batch__isnull=True
        )
        .select_related("customer")
        .order_by("qualified_at", "id")
    )
    unpaid_count = unpaid_events_qs.count()

    if batch_size_to_create is None:
        # Default to the largest possible multiple of std_batch_size
        batch_size_to_create = (unpaid_count // std_batch_size) * std_batch_size

    batch_size_to_create = int(batch_size_to_create)

    if batch_size_to_create < std_batch_size:
        raise ValueError(f"Batch size must be at least {std_batch_size}.")

    if batch_size_to_create % std_batch_size != 0:
        raise ValueError(f"Batch size must be an exact multiple of {std_batch_size} (e.g. 5, 10, 15).")

    if unpaid_count < batch_size_to_create:
        raise ValueError(
            f"Agent only has {unpaid_count} unpaid qualified customers, but {batch_size_to_create} requested."
        )

    # Oldest events first (FIFO)
    events_to_batch = list(unpaid_events_qs[:batch_size_to_create])
    total_amount = Decimal(str(batch_size_to_create)) * incentive_amount

    with transaction.atomic():
        # Generate unique batch number
        now = timezone.now()
        date_str = now.strftime("%Y%m%d")
        existing_today = AgentPayoutBatch.objects.filter(batch_number__startswith=f"BATCH-{date_str}").count()
        batch_number = f"BATCH-{date_str}-{(existing_today + 1):03d}"

        batch = AgentPayoutBatch.objects.create(
            batch_number=batch_number,
            agent=agent,
            amount=total_amount,
            customer_count=batch_size_to_create,
            status="pending",
            notes=notes,
        )

        # Associate customers and update events
        customers_to_add = [ev.customer for ev in events_to_batch]
        batch.customers.add(*customers_to_add)

        event_ids = [ev.id for ev in events_to_batch]
        AgentQualificationEvent.objects.filter(id__in=event_ids).update(payout_batch=batch)

        try:
            SystemLog.objects.create(
                table_name="AgentPayoutBatch",
                record_id=str(batch.id),
                action="CREATE_PAYOUT_BATCH",
                changed_by=user.username if user else "system",
                target_name=agent.name,
                old_data="",
                new_data=f"Batch: {batch_number}\nAmount: ₱{total_amount:,.2f}\nCustomers: {batch_size_to_create}",
            )
        except Exception:
            pass

        return batch


def mark_agent_payout_batch_paid(batch, user, reference_no="", notes=""):
    """
    Marks an AgentPayoutBatch as PAID:
    - Sets batch status='paid', paid_by=user, paid_at=now, reference_no
    - Updates all linked AgentQualificationEvents to status='paid_out'
    - Permanent history preserved.
    """
    if batch.status == "paid":
        return batch

    with transaction.atomic():
        batch.status = "paid"
        batch.paid_by = user
        batch.paid_at = timezone.now()
        if reference_no:
            batch.reference_no = reference_no
        if notes:
            batch.notes = (f"{batch.notes}\n{notes}").strip() if batch.notes else notes
        batch.save()

        # Update linked events to paid_out
        batch.events.update(status="paid_out")

        try:
            SystemLog.objects.create(
                table_name="AgentPayoutBatch",
                record_id=str(batch.id),
                action="MARK_PAYOUT_PAID",
                changed_by=user.username if user else "system",
                target_name=batch.agent.name,
                old_data="status=pending",
                new_data=f"status=paid\nAmount: ₱{batch.amount:,.2f}\nRef: {reference_no}\nPaid By: {user.username if user else 'Unknown'}",
            )
        except Exception:
            pass

        return batch
