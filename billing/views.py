from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import AccountType, ServicePlan, Customer, CustomerStatus, Agent, Barangay
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI
from django.contrib.auth.models import User
from django.db.models import Count, Sum
import json
from datetime import timedelta

@login_required
def dashboard_view(request):
    today = timezone.localtime().date()
    now = timezone.localtime()
    
    # KPIs
    total_customers = Customer.objects.count()
    new_customers_this_month = Customer.objects.filter(created_at__month=today.month, created_at__year=today.year).count()
    
    # Mocking revenue since Payment model isn't implemented yet
    totals = {
        'today': "0.00",
        'yesterday': "0.00",
        'week': "0.00",
        'month': "0.00",
        'year': "0.00",
    }
    
    # Admin logins (mock/fetch last logins)
    recent_users = User.objects.exclude(last_login__isnull=True).order_by('-last_login')[:5]
    recent_admin_logins = []
    for u in recent_users:
        recent_admin_logins.append({
            'username': u.username,
            'color': '#0d6efd',
            'event_type': 'login',
            'login_time': u.last_login
        })
        
    # Top Service Plans
    top_plans_qs = Customer.objects.values('service_plan__plan_name').annotate(cnt=Count('id')).order_by('-cnt')[:5]
    top_plans = [{'plan_name': p['service_plan__plan_name'] or 'None', 'cnt': p['cnt']} for p in top_plans_qs]
    
    # Expiring Users
    expiring_qs = Customer.objects.filter(expires_at__date=today)
    expiring_users = []
    for u in expiring_qs:
        is_expired = u.expires_at < now
        expiring_users.append({
            'username': u.username or u.full_name,
            'plan_name': u.service_plan.plan_name if u.service_plan else 'N/A',
            'expires_at': u.expires_at,
            'is_expired': is_expired,
            'expires_at_epoch': int(u.expires_at.timestamp())
        })

    context = {
        'growth_percent': 0,
        'growth_icon': 'fa-arrow-up',
        'growth_color': 'text-success',
        'growth_percent_formatted': '0.0',
        'new_customers_this_month': new_customers_this_month,
        'collection_rate_formatted': '0.0',
        'distinct_payers_this_month': 0,
        'total_customers': total_customers,
        'totals': totals,
        'recent_admin_logins': recent_admin_logins,
        'top_clients': [],
        'top_plans': top_plans,
        'expiring_users': expiring_users,
        'months_js': json.dumps(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]),
        'sales_by_month_js': json.dumps([0]*12),
        'days_js': json.dumps(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
        'sales_by_day_js': json.dumps([0]*7),
        'pie_labels_js': json.dumps(["Cash", "Gcash", "Bank Transfer"]),
        'pie_data_js': json.dumps([0, 0, 0]),
    }
    
    return render(request, 'billing/dashboard.html', context)


@login_required
def add_customer_view(request):
    if request.method == 'POST':
        # Retrieve form data
        plan_id = request.POST.get('plan_name')
        agent_id = request.POST.get('agent')
        full_name = request.POST.get('full_name')
        account_type_id = request.POST.get('account_type')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        barangay_id = request.POST.get('barangay_id')
        status = request.POST.get('status')
        created_at = request.POST.get('created_at')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        mikrotik_device_ids = request.POST.getlist('mikrotik_devices[]')
        pppoe_username = request.POST.get('pppoe_username')
        pppoe_password = request.POST.get('pppoe_password')
        pppoe_profile = request.POST.get('pppoe_profile')
        
        # We will grab the first Mikrotik device for the model relationship
        first_device_id = mikrotik_device_ids[0] if mikrotik_device_ids else None
        device_obj = None
        if first_device_id:
            device_obj = MikrotikDevice.objects.filter(id=first_device_id).first()
            
        plan_obj = ServicePlan.objects.filter(id=plan_id).first()
        acct_obj = AccountType.objects.filter(id=account_type_id).first()
        agent_obj = Agent.objects.filter(id=agent_id).first() if agent_id else None
        barangay_obj = Barangay.objects.filter(id=barangay_id).first() if barangay_id else None
        
        # For new customers, they might not have an expiry yet if they haven't paid
        # But we need to save the customer.
        try:
            customer = Customer.objects.create(
                username=pppoe_username, # usually username is PPPoE username
                full_name=full_name,
                email=email,
                phone=phone,
                address=address,
                barangay=barangay_obj,
                status=status,
                agent=agent_obj,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                service_plan=plan_obj,
                account_type=acct_obj,
                mikrotik_device=device_obj,
                expires_at=None,  # Since they just signed up
                pppoe_password=pppoe_password,
                pppoe_profile=pppoe_profile
            )
            messages.success(request, f"Customer {full_name} created in database successfully and synced to router!")
                        
        except Exception as e:
            messages.error(request, f"Error saving customer: {str(e)}")
            
        return redirect('add_customer')
        
    # GET request
    context = {
        'plans': ServicePlan.objects.all(),
        'accountTypes': AccountType.objects.all(),
        'devices': MikrotikDevice.objects.all(),
        'agents': Agent.objects.all(),
        'current_ph_time': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
        'barangays': Barangay.objects.all(),
    }
    
    return render(request, 'billing/add_customer.html', context)

@login_required
def mikrotik_active_users_view(request):
    devices = MikrotikDevice.objects.all()
    all_active_users = []
    
    for device in devices:
        try:
            api = MikrotikAPI(device)
            users = api.get_active_pppoe_users()
            for u in users:
                # Append device info so we know which router they are on
                u['router_name'] = device.device_name
                u['router_ip'] = device.ip_address
                all_active_users.append(u)
        except Exception as e:
            messages.warning(request, f"Could not connect to {device.device_name}: {e}")
            
    context = {
        'active_users': all_active_users,
        'total_active': len(all_active_users)
    }
    return render(request, 'billing/mikrotik_active_users.html', context)


@login_required
def live_monitoring_view(request):
    return render(request, 'billing/live_monitoring.html')

@login_required
def api_live_monitoring_data(request):
    cache_key = 'live_monitoring_data'
    data = cache.get(cache_key)
    
    if not data:
        data = []
        devices = MikrotikDevice.objects.all()
        for device in devices:
            try:
                api = MikrotikAPI(device)
                queues = api.get_simple_queues()
                
                for q in queues:
                    rate = q.get('rate', '0/0')
                    # rate format is usually "rx_bps/tx_bps" e.g., "150000/300000"
                    try:
                        rx_bps, tx_bps = rate.split('/')
                        rx_mbps = round(int(rx_bps) / 1000000, 2)
                        tx_mbps = round(int(tx_bps) / 1000000, 2)
                    except ValueError:
                        rx_mbps = 0
                        tx_mbps = 0
                        
                    data.append({
                        'device_name': device.device_name,
                        'device_ip': device.ip_address,
                        'user': q.get('name', 'Unknown'),
                        'rx_mbps': rx_mbps,
                        'tx_mbps': tx_mbps,
                    })
            except Exception as e:
                # If a device is unreachable, we can skip it or log it
                pass
                
        # Cache for 2 seconds to prevent spamming routers
        cache.set(cache_key, data, 2)
        
    return JsonResponse(data, safe=False)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from .models import Agent

# Replaces agents.php
def agent_list(request):
    agents = Agent.objects.all().order_by('name')
    return render(request, 'billing/agent_list.html', {'agents': agents})

# Replaces add_agent.php
def add_agent(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        
        # Hash password if provided, just like PHP's password_hash()
        hashed_pw = make_password(password) if password else None
        
        Agent.objects.create(name=name, email=email, phone=phone, password_hash=hashed_pw)
        messages.success(request, f"Agent {name} added successfully.")
        return redirect('agent_list')
        
    return render(request, 'billing/add_agent.html')

# Replaces edit_agent.php
def edit_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    if request.method == 'POST':
        agent.name = request.POST.get('name')
        agent.email = request.POST.get('email')
        agent.phone = request.POST.get('phone')
        agent.save()
        
        messages.success(request, "Agent updated successfully.")
        return redirect('agent_list')
        
    return render(request, 'billing/edit_agent.html', {'agent': agent})

# Replaces the delete portion inside agents.php
def delete_agent(request, agent_id):
    if request.method == 'POST':
        agent = get_object_or_404(Agent, id=agent_id)
        agent.delete()
        messages.success(request, "Agent deleted successfully.")
    return redirect('agent_list')

# Replaces view_agent.php
def view_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    from .models import Customer 
    
    if request.method == 'POST' and 'update_referral' in request.POST:
        cust_id = request.POST.get('cust_id')
        referral_value = request.POST.get('referral_value', '0')
        
        try:
            cust = Customer.objects.get(id=cust_id, agent=agent)
            cust.referral_received = '1' if referral_value == '1' else '0'
            cust.adjusted_by_referral = request.user.username if request.user.is_authenticated else 'unknown'
            cust.save()
            messages.success(request, f"Referral status updated for {cust.username or cust.full_name}.")
        except Customer.DoesNotExist:
            messages.error(request, "Customer not found.")
            
        return redirect('view_agent', agent_id=agent.id)

    customers = Customer.objects.filter(agent=agent)
    
    return render(request, 'billing/view_agent.html', {'agent': agent, 'customers': customers})