from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from billing.models import Agent, Customer, Barangay, SubscriptionPlan, Notification
import re

@login_required
def agent_dashboard(request):
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        messages.error(request, "Your account is not linked to an Agent profile.")
        return redirect('dashboard')
    
    # Get all customers referred by this agent
    prospects = Customer.objects.filter(agent=agent).order_by('-created_at')
    qualified_count = agent.qualified_customers_count
    target_count = 5
    progress_pct = min(100, int((qualified_count / target_count) * 100))
    is_cashout_eligible = agent.is_cashout_eligible
    
    context = {
        'agent': agent,
        'prospects': prospects,
        'claimable_commission': agent.claimable_commission,
        'qualified_count': qualified_count,
        'target_count': target_count,
        'progress_pct': progress_pct,
        'is_cashout_eligible': is_cashout_eligible,
        'barangays': Barangay.objects.all(),
        'current_tab': 'agents',
    }
    return render(request, 'billing/agent_dashboard.html', context)

@login_required
def agent_request_cashout(request):
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        messages.error(request, "Your account is not linked to an Agent profile.")
        return redirect('dashboard')

    if request.method == "POST":
        # Strict backend threshold validation: 5 qualified customers AND ₱2,500
        if not agent.is_cashout_eligible:
            messages.error(
                request,
                f"Cash-out gated: You need at least 5 qualifying subscribers and ₱2,500.00 claimable balance. "
                f"Current: {agent.qualified_customers_count}/5 qualified subscribers (₱{agent.claimable_commission:,.2f})."
            )
            return redirect('agent_dashboard')

        from billing.models import Notification, SystemLog
        Notification.objects.create(
            title=f"💰 Agent Cash-Out Request: {agent.name}",
            message=f"Agent {agent.name} has requested a commission payout of ₱{agent.claimable_commission:,.2f} ({agent.qualified_customers_count} qualified subscribers).",
            notification_type="payment",
            link=f"/agents/view/{agent.id}/"
        )
        try:
            SystemLog.objects.create(
                user=request.user.username,
                action=f"Agent '{agent.name}' submitted cash-out request for ₱{agent.claimable_commission:,.2f}",
                ip_address=request.META.get("REMOTE_ADDR", ""),
            )
        except Exception:
            pass

        messages.success(request, f"Cash-out request for ₱{agent.claimable_commission:,.2f} submitted to Admin! Accounting will review and disburse your commission.")
        return redirect('agent_dashboard')

    return redirect('agent_dashboard')

@login_required
def agent_add_prospect(request):
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        messages.error(request, "Your account is not linked to an Agent profile.")
        return redirect('dashboard')
        
    if request.method == "POST":
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        barangay_id = request.POST.get('barangay')
        plan_id = request.POST.get('plan_id')
        preferred_install_date = request.POST.get('preferred_installation_date') or None
        id_type = request.POST.get('id_type', '').strip()
        id_number = request.POST.get('id_number', '').strip()
        preferred_payment = request.POST.get('preferred_payment_method', 'cash').strip().lower()
        if preferred_payment not in ['cash', 'gcash']:
            preferred_payment = 'cash'
        
        # Validation
        if not full_name or not phone or not barangay_id:
            messages.error(request, "Please fill in all required fields (Name, Contact Number, and Barangay).")
            return redirect('agent_add_prospect')
            
        # Clean phone number
        phone = re.sub(r'\D', '', phone)
        if phone.startswith('0'):
            phone = '63' + phone[1:]
        elif not phone.startswith('63'):
            phone = '63' + phone
            
        barangay = get_object_or_404(Barangay, id=barangay_id)
        plan = SubscriptionPlan.objects.filter(id=plan_id).first() if plan_id else None
        
        # Create Prospect (Customer in 'pending' status)
        # Note: agent_lock_until is strictly set at Stage 5 Admin Approval, not at prospect intake!
        prospect = Customer.objects.create(
            full_name=full_name,
            phone=phone,
            address=address,
            barangay=barangay,
            plan=plan,
            preferred_installation_date=preferred_install_date,
            id_type=id_type,
            id_number=id_number,
            preferred_payment_method=preferred_payment,
            agent=agent,
            status='pending',
            installation_status='pending',
            agent_lock_until=None,
            is_verified=False
        )
        
        if agent:
            # Create staff notification for new agent prospect
            Notification.objects.create(
                title=f"New Prospect from Agent {agent.name}",
                message=f"{agent.name} submitted applicant {full_name} ({barangay.name}) for verification.",
                notification_type="dispatch",
                link="/dispatch/pipeline/1-verification/"
            )
            messages.success(request, f"Prospect {full_name} submitted successfully! Dispatch staff has been notified to verify the application.")
            return redirect('agent_dashboard')
        else:
            messages.success(request, f"Walk-in Prospect {full_name} submitted successfully for Stage 1 verification!")
            return redirect('dispatch_verification')
        
    context = {
        'agent': agent,
        'barangays': Barangay.objects.all(),
        'plans': SubscriptionPlan.objects.all(),
        'today': timezone.now().date().strftime("%Y-%m-%d"),
        'current_tab': 'agents',
    }
    return render(request, 'billing/agent_add_prospect.html', context)
