from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from billing.models import Agent, Customer, Prospect, Barangay, SubscriptionPlan, Notification, SystemLog
from billing.validators import normalize_ph_phone


@login_required
def agent_dashboard(request):
    """
    Agent Portal Dashboard:
    Minimal mobile-friendly layout for sales agents.
    Strictly displays the agent's own referrals and incentive progress.
    """
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        messages.error(request, "Your account is not linked to an Agent profile.")
        return redirect("dashboard")

    # Strict isolation: Fetch ONLY referrals submitted by or assigned to this agent
    prospects = Prospect.objects.filter(agent=agent).select_related("barangay", "plan", "converted_customer").order_by("-created_at")

    qualified_count = getattr(agent, "qualified_customers_count", 0)
    target_count = 5
    progress_pct = min(100, int((qualified_count / target_count) * 100)) if target_count else 0
    is_cashout_eligible = getattr(agent, "is_cashout_eligible", False)

    context = {
        "agent": agent,
        "prospects": prospects,
        "claimable_commission": getattr(agent, "claimable_commission", 0.0),
        "qualified_count": qualified_count,
        "target_count": target_count,
        "progress_pct": progress_pct,
        "is_cashout_eligible": is_cashout_eligible,
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

        # Duplicate detection check
        duplicate_flag = False
        duplicate_notes_list = []
        duplicate_of = None

        existing_cust = Customer.objects.filter(Q(phone=phone) | Q(full_name__iexact=full_name)).first()
        if existing_cust:
            duplicate_flag = True
            duplicate_notes_list.append(f"Matches existing subscriber: {existing_cust.full_name} ({existing_cust.phone})")

        existing_prospect = Prospect.objects.filter(Q(phone=phone) | Q(full_name__iexact=full_name)).exclude(status="declined").first()
        if existing_prospect:
            duplicate_flag = True
            duplicate_notes_list.append(f"Matches existing referral lead: {existing_prospect.full_name} ({existing_prospect.phone})")
            duplicate_of = existing_prospect

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
            duplicate_notes="; ".join(duplicate_notes_list) if duplicate_notes_list else None,
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
        try:
            SystemLog.objects.create(
                user=request.user.username,
                action=f"Agent '{agent.name}' submitted cash-out request for ₱{agent.claimable_commission:,.2f}",
                ip_address=request.META.get("REMOTE_ADDR", ""),
            )
        except Exception:
            pass

        messages.success(request, f"Cash-out request for ₱{agent.claimable_commission:,.2f} submitted to Admin!")
        return redirect("agent_dashboard")

    return redirect("agent_dashboard")
