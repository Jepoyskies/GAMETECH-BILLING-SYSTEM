from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from billing.models import Agent, Customer, Barangay
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
    
    context = {
        'agent': agent,
        'prospects': prospects,
        'claimable_commission': agent.claimable_commission,
        'barangays': Barangay.objects.all(),
        'current_tab': 'agents',
    }
    return render(request, 'billing/agent_dashboard.html', context)

@login_required
def agent_add_prospect(request):
    try:
        agent = request.user.agent_profile
    except Agent.DoesNotExist:
        messages.error(request, "Your account is not linked to an Agent profile.")
        return redirect('dashboard')
        
    if request.method == "POST":
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        barangay_id = request.POST.get('barangay')
        
        # Validation
        if not full_name or not phone or not barangay_id:
            messages.error(request, "Please fill in all required fields.")
            return redirect('agent_dashboard')
            
        # Clean phone number
        phone = re.sub(r'\D', '', phone)
        if phone.startswith('0'):
            phone = '63' + phone[1:]
        elif not phone.startswith('63'):
            phone = '63' + phone
            
        barangay = get_object_or_404(Barangay, id=barangay_id)
        
        # Create Prospect (Customer in 'pending' status)
        # Lock them for 60 days
        lock_date = timezone.now() + timedelta(days=60)
        
        prospect = Customer.objects.create(
            full_name=full_name,
            phone=phone,
            address=address,
            barangay=barangay,
            agent=agent,
            status='pending',
            installation_status='pending',
            agent_lock_until=lock_date,
            is_verified=False
        )
        
        messages.success(request, f"Prospect {full_name} added successfully! Staff will verify the application.")
        return redirect('agent_dashboard')
        
    context = {
        'agent': agent,
        'barangays': Barangay.objects.all(),
        'current_tab': 'agents',
    }
    return render(request, 'billing/agent_add_prospect.html', context)
