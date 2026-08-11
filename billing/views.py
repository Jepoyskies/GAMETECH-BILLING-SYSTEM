from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Customer, ServicePlan, AccountType
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
        agent = request.POST.get('agent')
        full_name = request.POST.get('full_name')
        account_type_id = request.POST.get('account_type')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
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
        
        # For new customers, they might not have an expiry yet if they haven't paid
        # But we need to save the customer.
        try:
            customer = Customer.objects.create(
                username=pppoe_username, # usually username is PPPoE username
                full_name=full_name,
                email=email,
                phone=phone,
                address=address,
                status=status,
                agent=agent,
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
        'agents': ['Agent 1', 'Agent 2', 'Internal'], # Mock agents list for now
        'current_ph_time': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
        'barangays': [], # Mock empty for now
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
