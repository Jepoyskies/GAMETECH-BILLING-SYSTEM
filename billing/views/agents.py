from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from billing.models import (
    Agent,
    Customer,
    Prospect,
    Barangay,
    SubscriptionPlan,
    Notification,
    SystemLog,
    AgentQualificationEvent,
    AgentPayoutBatch,
    IncentiveSetting,
)
from billing.validators import normalize_ph_phone, check_customer_or_prospect_duplicate
from billing.security import log_sensitive_operation
from billing.services.incentives import (
    get_agent_incentive_summary,
    get_customer_qualifying_paid_total,
)


@login_required
def agent_dashboard(request):
    """
    Agent Portal Dashboard:
    Minimal mobile-friendly layout for sales agents.
    Strictly displays the agent's own referrals, 2nd-month qualifying progress,
    unlock date, and permanent payout history from the incentive ledger.
    """
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        messages.error(request, "Your account is not linked to an Agent profile.")
        return redirect("dashboard")

    # Strict isolation: Fetch ONLY referrals submitted by or assigned to this agent
    prospects = (
        Prospect.objects.filter(agent=agent)
        .select_related("barangay", "plan", "converted_customer", "converted_customer__plan")
        .order_by("-created_at")
    )

    summary = get_agent_incentive_summary(agent)
    batch_size = summary["batch_size"]
    progress_count = summary["progress_to_next"]
    progress_pct = min(100, int((progress_count / batch_size) * 100)) if batch_size else 0

    # Decorate prospects with qualification and payment progress
    for p in prospects:
        cust = p.converted_customer
        if cust:
            event = AgentQualificationEvent.objects.filter(customer=cust, agent=agent).first()
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
                is_cancelled = (
                    cust.status in ["closed_not_installed", "pull out"]
                    or cust.installation_status == "closed_not_installed"
                )
                if is_cancelled:
                    p.qualification_status = "cancelled"
                    p.progress_text = "Cancelled (Ineligible)"
                    p.is_qualified = False
                else:
                    net_paid = get_customer_qualifying_paid_total(cust)
                    plan_price = cust.plan.price if cust.plan and cust.plan.price else Decimal("0.00")
                    threshold = Decimal("2.00") * plan_price

                    if net_paid >= threshold and plan_price > 0:
                        p.qualification_status = "qualified"
                        p.progress_text = "Qualified (₱500)"
                        p.is_qualified = True
                    elif net_paid > plan_price and plan_price > 0:
                        paid_2nd_month = net_paid - plan_price
                        rem_2nd_month = threshold - net_paid
                        p.qualification_status = "in_progress"
                        p.progress_text = f"PHP {paid_2nd_month:,.0f} paid, PHP {rem_2nd_month:,.0f} remaining"
                        p.is_qualified = False
                    elif net_paid > 0 and plan_price > 0:
                        p.qualification_status = "in_progress"
                        p.progress_text = f"PHP 0 paid, PHP {plan_price:,.0f} remaining"
                        p.is_qualified = False
                    else:
                        p.qualification_status = "pending_payment"
                        p.progress_text = "Pending 1st Payment"
                        p.is_qualified = False

            p.unlock_date = cust.agent_lock_until
        else:
            p.qualification_status = "prospect"
            p.progress_text = "Pending Onboarding"
            p.unlock_date = None

    payout_history = AgentPayoutBatch.objects.filter(agent=agent).order_by("-created_at")

    context = {
        "agent": agent,
        "prospects": prospects,
        "claimable_commission": summary["claimable_amount"],
        "unpaid_qualified": summary["unpaid_qualified"],
        "total_qualified": summary["total_qualified"],
        "batch_size": batch_size,
        "progress_count": progress_count,
        "progress_pct": progress_pct,
        "is_cashout_eligible": summary["is_cashout_eligible"],
        "payout_history": payout_history,
        "barangays": Barangay.objects.all(),
    }
    return render(request, "billing/agent_portal/dashboard.html", context)



@login_required
def agent_add_prospect(request):
    """
    Allows an agent to submit a new referral lead into the Prospect table.
    Performs duplicate detection, Philippine phone normalization, and creates
    a high-priority staff bell notification.
    """
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        messages.error(request, "Your account is not linked to an Agent profile.")
        return redirect("dashboard")

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        phone_raw = request.POST.get("phone", "").strip()
        email = (request.POST.get("email") or "").strip() or None
        address = request.POST.get("address", "").strip()
        barangay_id = request.POST.get("barangay")
        plan_id = request.POST.get("plan_id")
        preferred_install_date = request.POST.get("preferred_installation_date") or None
        id_type = request.POST.get("id_type", "").strip()
        id_number = request.POST.get("id_number", "").strip()
        preferred_payment = request.POST.get("preferred_payment_method", "cash").strip().lower()
        if preferred_payment not in ["cash", "gcash"]:
            preferred_payment = "cash"
        notes = request.POST.get("notes", "").strip()

        if not full_name or not phone_raw or not barangay_id:
            messages.error(request, "Please fill in all required fields (Name, Contact Number, and Barangay).")
            return redirect("agent_add_prospect")

        try:
            phone = normalize_ph_phone(phone_raw, required=True)
        except Exception:
            phone = phone_raw

        barangay = get_object_or_404(Barangay, id=barangay_id)
        plan = SubscriptionPlan.objects.filter(id=plan_id).first() if plan_id else None

        # Duplicate detection check using centralized validator (phone OR normalized name + address)
        is_dup, dup_reason, dup_obj = check_customer_or_prospect_duplicate(
            phone=phone, full_name=full_name, address=address
        )
        duplicate_flag = is_dup
        duplicate_notes = dup_reason
        duplicate_of = dup_obj if isinstance(dup_obj, Prospect) else None

        prospect = Prospect.objects.create(
            agent=agent,
            submitted_by=request.user,
            full_name=full_name,
            phone=phone,
            email=email,
            address=address,
            barangay=barangay,
            plan=plan,
            preferred_installation_date=preferred_install_date,
            id_type=id_type,
            id_number=id_number,
            preferred_payment_method=preferred_payment,
            notes=notes,
            status="submitted",
            duplicate_flag=duplicate_flag,
            duplicate_notes=duplicate_notes,
            duplicate_of=duplicate_of,
        )

        # Bell Notification to Staff
        try:
            Notification.objects.create(
                title=f"New Referral from Agent {agent.name}",
                message=f"Agent {agent.name} submitted applicant {full_name} ({barangay.name}).",
                notification_type="prospect",
                link=f"/prospects/{prospect.id}/",
            )
        except Exception:
            pass

        messages.success(
            request,
            f"Referral application for {full_name} submitted successfully! Staff has been notified to verify the application.",
        )
        return redirect("agent_dashboard")

    context = {
        "agent": agent,
        "barangays": Barangay.objects.all(),
        "plans": SubscriptionPlan.objects.all(),
        "today": timezone.now().date().strftime("%Y-%m-%d"),
    }
    return render(request, "billing/agent_portal/submit_prospect.html", context)


@login_required
def agent_edit_prospect(request, prospect_id):
    """
    Allows referring agent to edit prospect details ONLY IF staff has not yet opened/reviewed it.
    Once opened_by_staff_at is set, editing is strictly locked.
    """
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        messages.error(request, "Your account is not linked to an Agent profile.")
        return redirect("dashboard")

    prospect = get_object_or_404(Prospect, id=prospect_id, agent=agent)

    # Edit lockout check
    if prospect.opened_by_staff_at is not None or prospect.status != "submitted":
        messages.error(
            request,
            "Editing locked: Staff has already opened or reviewed this referral lead.",
        )
        return redirect("agent_dashboard")

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        phone_raw = request.POST.get("phone", "").strip()
        email = (request.POST.get("email") or "").strip() or None
        address = request.POST.get("address", "").strip()
        barangay_id = request.POST.get("barangay")
        plan_id = request.POST.get("plan_id")
        preferred_install_date = request.POST.get("preferred_installation_date") or None
        id_type = request.POST.get("id_type", "").strip()
        id_number = request.POST.get("id_number", "").strip()
        preferred_payment = request.POST.get("preferred_payment_method", "cash").strip().lower()
        if preferred_payment not in ["cash", "gcash"]:
            preferred_payment = "cash"
        notes = request.POST.get("notes", "").strip()

        if not full_name or not phone_raw or not barangay_id:
            messages.error(request, "Please fill in all required fields.")
            return redirect("agent_edit_prospect", prospect_id=prospect.id)

        try:
            phone = normalize_ph_phone(phone_raw, required=True)
        except Exception:
            phone = phone_raw

        barangay = get_object_or_404(Barangay, id=barangay_id)
        plan = SubscriptionPlan.objects.filter(id=plan_id).first() if plan_id else None

        prospect.full_name = full_name
        prospect.phone = phone
        prospect.email = email
        prospect.address = address
        prospect.barangay = barangay
        prospect.plan = plan
        prospect.preferred_installation_date = preferred_install_date
        prospect.id_type = id_type
        prospect.id_number = id_number
        prospect.preferred_payment_method = preferred_payment
        prospect.notes = notes

        # Recheck duplicate flag
        duplicate_flag = False
        duplicate_notes_list = []
        existing_cust = Customer.objects.filter(Q(phone=phone) | Q(full_name__iexact=full_name)).first()
        if existing_cust:
            duplicate_flag = True
            duplicate_notes_list.append(f"Matches existing subscriber: {existing_cust.full_name}")

        existing_prospect = Prospect.objects.filter(Q(phone=phone) | Q(full_name__iexact=full_name)).exclude(id=prospect.id).exclude(status="declined").first()
        if existing_prospect:
            duplicate_flag = True
            duplicate_notes_list.append(f"Matches existing referral: {existing_prospect.full_name}")
            prospect.duplicate_of = existing_prospect

        prospect.duplicate_flag = duplicate_flag
        prospect.duplicate_notes = "; ".join(duplicate_notes_list) if duplicate_notes_list else None
        prospect.save()

        messages.success(request, f"Referral application for {full_name} updated successfully.")
        return redirect("agent_dashboard")

    context = {
        "agent": agent,
        "prospect": prospect,
        "barangays": Barangay.objects.all(),
        "plans": SubscriptionPlan.objects.all(),
    }
    return render(request, "billing/agent_portal/edit_prospect.html", context)


@login_required
def agent_request_cashout(request):
    """
    Cash-out request action for agents.
    """
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        messages.error(request, "Your account is not linked to an Agent profile.")
        return redirect("dashboard")

    if request.method == "POST":
        if not getattr(agent, "is_cashout_eligible", False):
            messages.error(
                request,
                f"Cash-out gated: You need at least 5 qualifying subscribers and ₱2,500.00 claimable balance.",
            )
            return redirect("agent_dashboard")

        Notification.objects.create(
            title=f"💰 Agent Cash-Out Request: {agent.name}",
            message=f"Agent {agent.name} has requested a commission payout of ₱{agent.claimable_commission:,.2f}.",
            notification_type="payment",
            link=f"/agents/view/{agent.id}/",
        )
        # Was SystemLog.objects.create(user=..., ip_address=...) inside a bare
        # `except: pass`. SystemLog has neither field, so it raised TypeError and
        # was swallowed -- a cash-out request had NO audit trail at all, which is
        # a cash/ledger gap. See ERR-089 / ERR-091.
        log_sensitive_operation(
            "AGENT_CASHOUT_REQUEST",
            "Agent",
            agent.id,
            request.user.username,
            f"Agent '{agent.name}' requested cash-out of "
            f"PHP {agent.claimable_commission:,.2f} from IP "
            f"{request.META.get('REMOTE_ADDR', '')}.",
        )

        messages.success(request, f"Cash-out request for ₱{agent.claimable_commission:,.2f} submitted to Admin!")
        return redirect("agent_dashboard")

    return redirect("agent_dashboard")


@login_required
def staff_add_customer_for_agent(request, agent_id):
    """
    Staff action: 'Add Customer to this Agent' creates a Prospect (source='staff_on_behalf')
    that flows through the checklist -> customer form -> converted.
    """
    if hasattr(request.user, "agent_profile") and not request.user.is_staff:
        messages.error(request, "Access restricted.")
        return redirect("agent_dashboard")

    agent = get_object_or_404(Agent, id=agent_id)

    prospect = Prospect.objects.create(
        agent=agent,
        submitted_by=request.user,
        full_name=f"Applicant for {agent.name}",
        phone="",
        source="staff_on_behalf",
        status="under_review",
        opened_by_staff_at=timezone.now(),
        opened_by_staff_user=request.user,
    )
    messages.info(request, f"Onboarding referral initiated for Agent {agent.name}. Please complete the policy checklist and customer details.")
    return redirect(f"/customers/add/?prospect_id={prospect.id}&agent_id={agent.id}")
