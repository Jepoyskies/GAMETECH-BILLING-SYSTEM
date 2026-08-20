from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, permission_required
from .decorators import role_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime

from .models import (
    SystemAdmin, SubscriptionPlan, Agent, AccountType,
    Customer, Barangay, Payment, Rebate, SystemLog, SmsLog, CignalPlay
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar

def add_one_month(dt: datetime) -> datetime:
    """Adds exactly one calendar month to a datetime object."""
    month = dt.month
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)

def calculate_new_expiration_date(current_expiration_date: datetime, payment_amount: float, plan_monthly_price: float) -> datetime:
    if plan_monthly_price <= 0 or payment_amount <= 0:
        return current_expiration_date

    # 1. Full Month Exception
    if payment_amount == plan_monthly_price:
        return add_one_month(current_expiration_date)

    # 2. Price Per Day Calculation
    price_per_day = plan_monthly_price / 30.0

    # 3. Prorated Days Granted
    days_granted = payment_amount / price_per_day
    return current_expiration_date + timedelta(days=days_granted)


@login_required
def dashboard_view(request):
    if hasattr(request.user, 'role') and request.user.role == 'Agent':
        return redirect('customer_list')
        
    today = timezone.localtime().date()
    now = timezone.localtime()

    # KPIs
    total_customers = Customer.objects.count()
    new_customers_this_month = Customer.objects.filter(
        created_at__month=today.month, created_at__year=today.year).count()

    # Mocking revenue since Payment model isn't implemented yet
    totals = {
        'today': "0.00",
        'yesterday': "0.00",
        'week': "0.00",
        'month': "0.00",
        'year': "0.00",
    }

    # Admin logins (mock/fetch last logins)
    recent_users = User.objects.exclude(
        last_login__isnull=True).order_by('-last_login')[:5]
    recent_admin_logins = []
    for u in recent_users:
        recent_admin_logins.append({
            'username': u.username,
            'color': '#0d6efd',
            'event_type': 'login',
            'login_time': u.last_login
        })

    # Top Service Plans
    top_plans_qs = Customer.objects.values('plan__name').annotate(
        cnt=Count('id')).order_by('-cnt')[:5]
    top_plans = [{'plan_name': p['plan__name'] or 'None',
                  'cnt': p['cnt']} for p in top_plans_qs]

    # Expiring Users
    expiring_qs = Customer.objects.filter(expires_at__date=today)
    expiring_users = []
    for u in expiring_qs:
        is_expired = u.expires_at < now
        expiring_users.append({
            'username': u.pppoe_username or u.full_name,
            'plan_name': u.plan.name if u.plan else 'N/A',
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
        'sales_by_month_js': json.dumps([0] * 12),
        'days_js': json.dumps(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
        'sales_by_day_js': json.dumps([0] * 7),
        'pie_labels_js': json.dumps(["Cash", "Gcash", "Bank Transfer"]),
        'pie_data_js': json.dumps([0, 0, 0]),
    }

    return render(request, 'billing/dashboard.html', context)


@login_required
def mikrotik_active_users_data_api(request):
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
            # e is caught and used in the f-string
            messages.warning(
                request, f"Could not connect to {device.device_name}: {e}")

    context = {
        'active_users': all_active_users,
        'total_active': len(all_active_users)
    }
    return render(request, 'billing/partials/active_users_table.html', context)


@login_required
def mikrotik_active_users_view(request):
    from network_manager.models import MikrotikDevice
    from .models import Barangay
    devices = MikrotikDevice.objects.all().order_by('device_name')
    barangays = Barangay.objects.all().order_by('name')
    
    active_device_alerts = MikrotikDevice.objects.exclude(health_status='Excellent')
    active_barangay_alerts = Barangay.objects.exclude(health_status='Excellent')
    
    return render(request, 'billing/mikrotik_active_users.html', {
        'devices': devices, 
        'barangays': barangays,
        'active_device_alerts': active_device_alerts,
        'active_barangay_alerts': active_barangay_alerts
    })

@login_required
def update_network_health(request):
    if request.method == 'POST':
        scope = request.POST.get('scope')
        health_status = request.POST.get('health_status')
        health_reason = request.POST.get('health_reason')

        if scope == 'router':
            router_id = request.POST.get('router_id')
            if router_id:
                from network_manager.models import MikrotikDevice
                device = get_object_or_404(MikrotikDevice, id=router_id)
                device.health_status = health_status
                device.health_reason = health_reason
                device.save()
                messages.success(request, f"Health updated for router {device.device_name}.")
                
                send_sms = request.POST.get('send_sms') == '1'
                if send_sms and health_status in ['Outage', 'Poor', 'Moderate'] and health_reason:
                    message = f"Gametech Unli Fiber Advisory: {health_reason}"
                    from .models import Customer
                    affected_customers = Customer.objects.filter(mikrotik_device_id=device.id, status='active').exclude(phone__isnull=True).exclude(phone__exact='')
                    for customer in affected_customers:
                        send_semaphore_sms(customer.phone, message)
                        
        elif scope == 'barangay':
            barangay_ids = request.POST.getlist('barangay_id')
            if barangay_ids:
                from .models import Barangay
                barangays = Barangay.objects.filter(id__in=barangay_ids)
                names = []
                for barangay in barangays:
                    barangay.health_status = health_status
                    barangay.health_reason = health_reason
                    barangay.save()
                    names.append(barangay.name)
                    
                messages.success(request, f"Health updated for barangays: {', '.join(names)}.")
                
                send_sms = request.POST.get('send_sms') == '1'
                if send_sms and health_status in ['Outage', 'Poor', 'Moderate'] and health_reason:
                    message = f"Gametech Unli Fiber Advisory: {health_reason}"
                    from .models import Customer
                    affected_customers = Customer.objects.filter(barangay_id__in=barangay_ids, status='active').exclude(phone__isnull=True).exclude(phone__exact='')
                    for customer in affected_customers:
                        send_semaphore_sms(customer.phone, message)
                        
        elif scope == 'customer':
            customer_id = request.POST.get('customer_id')
            if customer_id:
                from .models import Customer
                customer = get_object_or_404(Customer, id=customer_id)
                customer.health_status = health_status
                customer.health_reason = health_reason
                customer.save()
                messages.success(request, f"Health updated for customer {customer.full_name}.")
                
                send_sms = request.POST.get('send_sms') == '1'
                if send_sms and health_status in ['Outage', 'Poor', 'Moderate'] and health_reason and customer.phone:
                    message = f"Gametech Unli Fiber Advisory: {health_reason}"
                    send_semaphore_sms(customer.phone, message)
                
    return redirect(request.META.get('HTTP_REFERER', 'live_monitoring'))

@login_required
def resolve_network_health(request, scope, item_id):
    if scope == 'router':
        from network_manager.models import MikrotikDevice
        device = get_object_or_404(MikrotikDevice, id=item_id)
        device.health_status = 'Excellent'
        device.health_reason = ''
        device.save()
        messages.success(request, f"Resolved network health for router {device.device_name}.")
    elif scope == 'barangay':
        from .models import Barangay
        barangay = get_object_or_404(Barangay, id=item_id)
        barangay.health_status = 'Excellent'
        barangay.health_reason = ''
        barangay.save()
        messages.success(request, f"Resolved network health for barangay {barangay.name}.")
    elif scope == 'customer':
        from .models import Customer
        customer = get_object_or_404(Customer, id=item_id)
        customer.health_status = 'Excellent'
        customer.health_reason = ''
        customer.save()
        messages.success(request, f"Resolved network health for customer {customer.full_name}.")
    return redirect(request.META.get('HTTP_REFERER', 'live_monitoring'))


@login_required
def live_monitoring_view(request):
    from .models import Barangay, Customer
    devices = MikrotikDevice.objects.all().order_by('device_name')
    barangays = Barangay.objects.all().order_by('name')
    customers = Customer.objects.filter(status='active').order_by('full_name')
    active_device_alerts = MikrotikDevice.objects.exclude(health_status='Excellent')
    active_barangay_alerts = Barangay.objects.exclude(health_status='Excellent')
    active_customer_alerts = Customer.objects.exclude(health_status='Excellent').filter(status='active')
    return render(request, 'billing/live_monitoring.html', {
        'devices': devices,
        'barangays': barangays,
        'customers': customers,
        'active_device_alerts': active_device_alerts,
        'active_barangay_alerts': active_barangay_alerts,
        'active_customer_alerts': active_customer_alerts
    })


@login_required
def api_live_monitoring_data(request):
    response_data = {
        'users': [],
        'routers': []
    }
    
    devices = MikrotikDevice.objects.all()
    for device in devices:
        try:
            api = MikrotikAPI(device)
            # Check Uplink Health by pinging 8.8.8.8
            uplink_status = 'Offline'
            uplink_ping = 'Timeout'
            try:
                ping_res = api._get_api().get_resource('/').call('ping', {'address': '8.8.8.8', 'count': '1'})
                if ping_res and len(ping_res) > 0:
                    result = ping_res[0]
                    loss = int(result.get('packet-loss', 100))
                    if loss == 100 or result.get('status') == 'no route to host' or result.get('status') == 'timeout':
                        uplink_status = 'Offline'
                        uplink_ping = 'Timeout'
                    else:
                        avg_rtt_str = result.get('avg-rtt', '0ms')
                        rtt_ms = int(avg_rtt_str.replace('ms', ''))
                        uplink_ping = f"{rtt_ms}ms"
                        if rtt_ms > 150:
                            uplink_status = 'Unstable'
                        else:
                            uplink_status = 'Online'
            except Exception as e:
                print(f"Ping Error on {device.device_name}: {e}")
                uplink_status = 'Offline'
                uplink_ping = 'Error'

            response_data['routers'].append({
                'id': device.id,
                'name': device.device_name,
                'ip': device.ip_address,
                'uplink_status': uplink_status,
                'uplink_ping': uplink_ping
            })

            active_users = api.get_active_pppoe_users()
            
            # Fetch traffic for all active PPPoE users directly from their dynamic interfaces
            interface_names = [f"<pppoe-{au.get('name')}>" for au in active_users if au.get('name')]
            traffic_data = api.get_interfaces_traffic(interface_names)
            
            # Map traffic data by clean username
            traffic_dict = {}
            for t in traffic_data:
                name = t.get('name', '')
                # Strip `<pppoe-` prefix and `>` suffix
                clean_name = name.strip('<>').replace('pppoe-', '', 1)
                
                try:
                    rx_bps = int(t.get('rx-bits-per-second', 0))
                    tx_bps = int(t.get('tx-bits-per-second', 0))
                    rx_mbps = round(rx_bps / 1000000, 2)
                    tx_mbps = round(tx_bps / 1000000, 2)
                except ValueError:
                    rx_mbps = 0
                    tx_mbps = 0
                    
                traffic_dict[clean_name] = {'rx_mbps': rx_mbps, 'tx_mbps': tx_mbps}

            # Build the output data
            for au in active_users:
                u_name = au.get('name', 'Unknown')
                user_ip = au.get('address', device.ip_address) # Actual assigned IP
                
                stats = traffic_dict.get(u_name, {'rx_mbps': 0, 'tx_mbps': 0})
                
                response_data['users'].append({
                    'device_name': device.device_name,
                    'device_ip': device.ip_address,
                    'ip': user_ip,
                    'user': u_name,
                    'rx_mbps': stats['rx_mbps'],
                    'tx_mbps': stats['tx_mbps'],
                    'uptime': au.get('uptime', '0s')
                })
        except Exception as e:
            # Device unreachable or API error
            pass
            
    return JsonResponse(response_data)


# ─────────────────────────────────────────────────
#  Subscription / Service Plans
# ─────────────────────────────────────────────────



# ─────────────────────────────────────────────────
#  Customer Subscriptions
# ─────────────────────────────────────────────────

@login_required
def subscription_plans_data_api(request):
    """Customer Subscriptions Dashboard API Data (Returns HTML Partial)."""
    # 1. Base Query
    customers = Customer.objects.select_related('plan', 'mikrotik_device').filter(
        pppoe_username__isnull=False,
    ).exclude(pppoe_username='').exclude(status='pull out')

    # 2. Extract Filters
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    device_filter = request.GET.get('device', '')
    connection_filter = request.GET.get('connection', '')

    # Sorting
    sort_column = request.GET.get('sort', 'expires_at')
    order = request.GET.get('order', 'desc').lower()

    valid_sorts = {
        'id': 'id',
        'username': 'pppoe_username',
        'full_name': 'full_name',
        'address': 'address',
        'expires_at': 'expires_at',
        'plan_name': 'plan__name',
        'price': 'plan__price',
        'device_name': 'mikrotik_device__device_name'
    }

    sort_field = valid_sorts.get(sort_column, 'expires_at')
    if order == 'desc':
        sort_field = f'-{sort_field}'

    # 3. Time bounds
    now = timezone.now()
    soon = now + timedelta(days=7)
    one_month_ago = now - timedelta(days=30)

    # 4. Apply Filters (except connection, which requires live MT data)
    if search:
        customers = customers.filter(
            Q(pppoe_username__icontains=search)
            | Q(full_name__icontains=search)
            | Q(address__icontains=search)
        )

    if status_filter == 'active':
        customers = customers.filter(expires_at__gt=soon)
    elif status_filter == 'expiring':
        customers = customers.filter(expires_at__gt=now, expires_at__lte=soon)
    elif status_filter == 'expired':
        customers = customers.filter(
            Q(expires_at__isnull=True)
            | Q(expires_at__lte=now, expires_at__gt=one_month_ago)
        )
    elif status_filter == 'inactive':
        customers = customers.filter(expires_at__lte=one_month_ago)

    if device_filter:
        customers = customers.filter(
            mikrotik_device__device_name=device_filter)

    # 5. Fetch MT Data
    connected_usernames = {}
    ppp_users_status = {}

    devices = MikrotikDevice.objects.all()
    for device in devices:
        try:
            api = MikrotikAPI(device)
            # Active Users
            active_users = api.get_active_pppoe_users()
            for au in active_users:
                name = au.get('name')
                if name:
                    connected_usernames[name] = {
                        'uptime': au.get('uptime', '')}

            # PPP Secrets
            secrets = api.get_ppp_secrets()
            for sec in secrets:
                name = sec.get('name')
                if name:
                    ppp_users_status[name] = {
                        'profile': sec.get('profile', ''),
                        'last_logged_out': sec.get('last-logged-out', '')
                    }
        except Exception:
            pass

    # Apply connection filter manually (since it requires live data)
    customer_list = list(customers.order_by(sort_field))

    if connection_filter == 'Connected':
        customer_list = [
            c for c in customer_list if c.pppoe_username in connected_usernames]
    elif connection_filter == 'Not Connected':
        customer_list = [
            c for c in customer_list if c.pppoe_username not in connected_usernames]

    # Calculate Summaries (based on filtered list)
    count_active = 0
    count_expiring = 0
    count_expired = 0
    count_inactive = 0
    count_connected = 0
    count_not_connected = 0

    for c in customer_list:
        # Connection
        if c.pppoe_username in connected_usernames:
            count_connected += 1
        else:
            count_not_connected += 1

        # Status
        if not c.expires_at:
            count_expired += 1
        elif c.expires_at <= one_month_ago:
            count_inactive += 1
        elif c.expires_at <= now:
            count_expired += 1
        elif c.expires_at <= soon:
            count_expiring += 1
        else:
            count_active += 1

    # 6. Pagination
    per_page = int(request.GET.get('per_page', 35))
    paginator = Paginator(customer_list, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Append MT data to page objects
    for c in page_obj:
        c.mt_connected = c.pppoe_username in connected_usernames
        c.mt_uptime = connected_usernames.get(
            c.pppoe_username, {}).get('uptime', '')
        c_secret = ppp_users_status.get(c.pppoe_username, {})
        c.mt_profile = c_secret.get('profile', '')
        c.mt_last_logged_out = c_secret.get('last_logged_out', '')

        # Calculate downtime if applicable
        c.mt_downtime = ''
        if not c.mt_connected and c.mt_last_logged_out:
            # MicroTik formats dates like "dec/31/2025 23:59:59" or similar
            # parsing is complex so we'll just display it as is or try to format
            # In the original PHP they rely on strtotime, Python needs more robust parsing
            c.mt_downtime = c.mt_last_logged_out

    # Unique devices for filter dropdown
    unique_devices = Customer.objects.filter(
        mikrotik_device__isnull=False
    ).values_list('mikrotik_device__device_name', flat=True).distinct()

    context = {
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'device_filter': device_filter,
        'connection_filter': connection_filter,
        'per_page': per_page,
        'sort': sort_column,
        'order': order.upper(),
        'unique_devices': unique_devices,

        'count_active': count_active,
        'count_expiring': count_expiring,
        'count_expired': count_expired,
        'count_inactive': count_inactive,
        'count_connected': count_connected,
        'count_not_connected': count_not_connected,

        'now': now,
        'soon': soon,
        'one_month_ago': one_month_ago,
    }

    return render(request, 'billing/partials/subscription_plans_table.html', context)


@login_required
def subscription_plans_view(request):
    """Customer Subscriptions Dashboard Skeleton View."""
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    device_filter = request.GET.get('device', '')
    connection_filter = request.GET.get('connection', '')
    per_page = int(request.GET.get('per_page', 10))
    sort = request.GET.get('sort', 'expires_at')
    order = request.GET.get('order', 'desc').lower()
    
    unique_devices = Customer.objects.filter(
        mikrotik_device__isnull=False
    ).values_list('mikrotik_device__device_name', flat=True).distinct()
    
    context = {
        'search': search,
        'status_filter': status_filter,
        'device_filter': device_filter,
        'connection_filter': connection_filter,
        'per_page': per_page,
        'sort': sort,
        'order': order.upper(),
        'unique_devices': unique_devices,
    }
    return render(request, 'billing/subscription_plans.html', context)


# Replaces agents.php

def agent_list(request):
    agents = Agent.objects.all().order_by('name')
    return render(request, 'billing/agents.html', {'agents': agents})

# Replaces add_agent.php

@login_required
@role_required(['Admin', 'Editor'])

def add_agent(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')

        # Hash password if provided, just like PHP's password_hash()
        hashed_pw = make_password(password) if password else None

        Agent.objects.create(name=name, email=email,
                             phone=phone, password_hash=hashed_pw)
        messages.success(request, f"Agent {name} added successfully.")
        return redirect('agent_list')

    return render(request, 'billing/add_agent.html')

# Replaces edit_agent.php

@login_required
@role_required(['Admin', 'Editor'])

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

@login_required
@role_required(['Admin', 'Editor'])

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
        referral_value = request.POST.get('referral_value')

        try:
            cust = Customer.objects.get(id=cust_id, agent=agent)
            if referral_value is not None:
                cust.referral_received = referral_value
            cust.adjusted_by_referral = request.user.username if request.user.is_authenticated else 'unknown'
            cust.save()
            messages.success(
                request, f"Referral status updated for {cust.pppoe_username or cust.full_name}.")
        except Customer.DoesNotExist:
            messages.error(request, "Customer not found.")

        return redirect('view_agent', agent_id=agent.id)

    customers = Customer.objects.filter(agent=agent)

    return render(request, 'billing/view_agent.html', {'agent': agent, 'customers': customers})


def plan_list(request):
    if hasattr(request.user, 'role') and request.user.role == 'Agent':
        return redirect('customer_list')
        
    plans = SubscriptionPlan.objects.all().order_by('price')
    return render(request, 'billing/service_plans.html', {'plans': plans})

@login_required
def sync_plans_from_mikrotik(request):
    from network_manager.models import MikrotikDevice
    from network_manager.services import MikrotikAPI
    import re
    
    device = MikrotikDevice.objects.first()
    if not device:
        messages.error(request, "No active MikroTik device found for sync.")
        return redirect('plan_list')
        
    try:
        api = MikrotikAPI(device)
        router_api = api._get_api()
        profiles = router_api.get_resource('/ppp/profile').get()
        api.connection.disconnect()
        
        synced_count = 0
        ignored_profiles = ['default', 'expired', 'default-encryption']
        
        for p in profiles:
            name = p.get('name')
            if name in ignored_profiles:
                continue
                
            rate_limit = p.get('rate-limit', '')
            speed_up = "1 Mbps"
            speed_down = "1 Mbps"
            
            if rate_limit:
                parts = rate_limit.split('/')
                if len(parts) == 2:
                    # convert 10M to 10 Mbps
                    def format_speed(s):
                        s = s.upper()
                        if 'M' in s:
                            return f"{s.replace('M', '')} Mbps"
                        if 'K' in s:
                            return f"{s.replace('K', '')} Kbps"
                        if 'G' in s:
                            return f"{s.replace('G', '')} Gbps"
                        return f"{s} bps"
                    speed_up = format_speed(parts[0])
                    speed_down = format_speed(parts[1])
            
            # Create or update plan
            plan, created = SubscriptionPlan.objects.get_or_create(
                name=name,
                defaults={
                    'speed_up': speed_up,
                    'speed_down': speed_down,
                    'price': 0.00,
                    'validity_days': 30
                }
            )
            if not created:
                plan.speed_up = speed_up
                plan.speed_down = speed_down
                plan.save()
                
            synced_count += 1
            
        messages.success(request, f"Successfully synced {synced_count} profiles from MikroTik.")
    except Exception as e:
        messages.error(request, f"MikroTik API Error during sync: {str(e)}")
        
    return redirect('plan_list')


@role_required(['Admin', 'Editor'])
@login_required
def add_plan(request):
    if request.method == 'POST':
        name = request.POST.get('plan_name')
        speed_up = request.POST.get('speed_up')
        speed_down = request.POST.get('speed_down')
        price = request.POST.get('price')
        validity_days = request.POST.get('validity_days')
        description = request.POST.get('description')

        SubscriptionPlan.objects.create(
            name=name,
            speed_up=speed_up,
            speed_down=speed_down,
            price=price,
            validity_days=validity_days,
            description=description
        )
        messages.success(request, f"Service plan '{name}' added successfully!")
        return redirect('plan_list')

    return render(request, 'billing/add_plan.html')


@role_required(['Admin', 'Editor'])
@login_required
def edit_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    if request.method == 'POST':
        plan.name = request.POST.get('plan_name')
        plan.speed_up = request.POST.get('speed_up')
        plan.speed_down = request.POST.get('speed_down')
        plan.price = request.POST.get('price')
        plan.validity_days = request.POST.get('validity_days')
        plan.description = request.POST.get('description')
        plan.save()

        messages.success(request, "Service plan updated successfully!")
        return redirect('plan_list')

    return render(request, 'billing/edit_plan.html', {'plan': plan})


@role_required(['Admin', 'Editor'])
@login_required
def delete_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    plan.delete()
    messages.success(request, "Service plan deleted successfully!")
    return redirect('plan_list')


@login_required
def staff_list(request):
    # Fetch all admins, ordered by the newest created
    staff_members = SystemAdmin.objects.all().order_by('-created_at')
    return render(request, 'billing/staff_and_admins.html', {'staff_members': staff_members})


@role_required(['Admin'])
@login_required
def add_staff(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        role = request.POST.get('role')
        status = request.POST.get('status')
        raw_password = request.POST.get('password')

        # Check if username or email already exists to prevent errors
        if User.objects.filter(username=username).exists() or SystemAdmin.objects.filter(username=username).exists():
            messages.error(request, "That username is already taken.")
            return redirect('add_staff')

        if User.objects.filter(email=email).exists() or SystemAdmin.objects.filter(email=email).exists():
            messages.error(request, "That email is already registered.")
            return redirect('add_staff')

        try:
            with transaction.atomic():
                # 1. Create the Django User (handles password hashing securely)
                user = User(
                    username=username,
                    email=email,
                    is_staff=True,  # Allows login to /admin/
                    is_active=(status == 'Active')
                )
                if role == 'Admin':
                    user.is_superuser = True
                user.set_password(raw_password)
                user.save() # This also triggers the signal to create EmployeeProfile

                # 2. Assign User to the correct RBAC Group
                from django.contrib.auth.models import Group
                group = Group.objects.filter(name=role).first()
                if group:
                    user.groups.add(group)

                # 3. Create the legacy SystemAdmin record for UI compatibility
                SystemAdmin.objects.create(
                    username=username,
                    full_name=full_name,
                    email=email,
                    role=role,
                    status=status,
                    password_hash=user.password
                )

            messages.success(request, f"Staff member '{full_name}' added successfully!")
            return redirect('staff_list')
        except Exception as e:
            messages.error(request, f"Error creating staff member: {str(e)}")
            return redirect('add_staff')

    return render(request, 'billing/add_staff.html')


@role_required(['Admin'])
@login_required
def edit_staff(request, pk):
    # Retrieve user role safely (fallback to Viewer to be safe)
    user_role = getattr(request.user, 'role', 'Viewer')
    
    # Strictly prohibit Viewers
    if user_role == 'Viewer':
        messages.error(request, "Access denied. Viewers are not permitted to edit staff details.")
        return redirect('staff_list')

    staff = get_object_or_404(SystemAdmin, pk=pk)
    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        role = request.POST.get('role')
        status = request.POST.get('status')
        raw_password = request.POST.get('password')

        # Check if username or email already exists to prevent errors
        if User.objects.filter(username=username).exclude(username=staff.username).exists() or \
           SystemAdmin.objects.filter(username=username).exclude(pk=pk).exists():
            messages.error(request, "That username is already taken.")
            return redirect('edit_staff', pk=pk)

        if User.objects.filter(email=email).exclude(email=staff.email).exists() or \
           SystemAdmin.objects.filter(email=email).exclude(pk=pk).exists():
            messages.error(request, "That email is already registered.")
            return redirect('edit_staff', pk=pk)

        try:
            with transaction.atomic():
                # Update or Create underlying Django User
                user = User.objects.filter(username=staff.username).first()
                if not user:
                    user = User(
                        username=username,
                        email=email,
                        is_staff=True,
                        is_active=(status == 'Active'),
                        is_superuser=(role == 'Admin')
                    )
                    if raw_password:
                        user.set_password(raw_password)
                    else:
                        user.set_unusable_password()
                    user.save()
                else:
                    user.username = username
                    user.email = email
                    user.is_active = (status == 'Active')
                    user.is_superuser = (role == 'Admin')
                    
                    if user_role == 'Admin' and raw_password:
                        user.set_password(raw_password)
                    
                    user.save()
                    
                # Update Group assignment
                user.groups.clear()
                from django.contrib.auth.models import Group
                group = Group.objects.filter(name=role).first()
                if group:
                    user.groups.add(group)

                # Update legacy staff user
                staff.username = username
                staff.full_name = full_name
                staff.email = email
                staff.role = role
                staff.status = status

                # Admins only: Override password if one is provided (for legacy compatibility)
                if user_role == 'Admin' and raw_password:
                    if user:
                        staff.password_hash = user.password
                    else:
                        staff.password_hash = make_password(raw_password)

                staff.save()

            messages.success(request, f"Staff member '{full_name}' updated successfully!")
            return redirect('staff_list')
        except Exception as e:
            messages.error(request, f"Error updating staff member: {str(e)}")
            return redirect('edit_staff', pk=pk)

    return render(request, 'billing/edit_staff.html', {'staff': staff})


@login_required
def customer_list(request):
    from network_manager.models import MikrotikDevice
    customers = Customer.objects.select_related(
        'plan', 'agent', 'barangay', 'mikrotik_device').all()
    devices = MikrotikDevice.objects.all().order_by('device_name')
    return render(request, 'billing/customer_list.html', {
        'customers': customers,
        'devices': devices
    })


@login_required
@role_required(['Admin', 'Agent', 'CSR'])
@permission_required('billing.add_customer', raise_exception=True)
def add_customer(request):
    if request.method == 'POST':
        Customer.objects.create(
            full_name=request.POST.get('full_name'),
            email=request.POST.get('email') or None,
            phone=request.POST.get('phone'),
            address=request.POST.get('address'),
            pppoe_username=request.POST.get('pppoe_username') or None,
            pppoe_password=request.POST.get('pppoe_password'),
            status='pending' if request.user.role == 'Agent' else request.POST.get('status', 'active'),
            plan_id=request.POST.get('plan_id'),
            mikrotik_device_id=request.POST.get('device_id') or None,
            agent_id=request.POST.get('agent_id'),
            barangay_id=request.POST.get('barangay_id'),
            account_type_id=request.POST.get('account_type_id') or None,
            latitude=request.POST.get('latitude') or None,
            longitude=request.POST.get('longitude') or None,
            cignalplay_no=request.POST.get('cignalplay_no'),
            cignalplay_date=request.POST.get('cignalplay_date') or None,
            created_form_by=request.user.username
        )
        messages.success(request, 'Customer added successfully!')
        return redirect('customer_list')
    context = {
        'plans': SubscriptionPlan.objects.all(),
        'devices': MikrotikDevice.objects.all(),
        'agents': Agent.objects.all(),
        'barangays': Barangay.objects.all(),
        'account_types': AccountType.objects.all(),
        'prefill_username': request.GET.get('pppoe_username', '')
    }
    return render(request, 'billing/add_customer.html', context)


@role_required(['Admin', 'Editor'])
@login_required
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        customer.full_name = request.POST.get('full_name')
        customer.email = request.POST.get('email') or None
        customer.phone = request.POST.get('phone')
        customer.address = request.POST.get('address')
        customer.pppoe_username = request.POST.get('pppoe_username') or None
        
        new_password = request.POST.get('pppoe_password')
        if new_password:
            customer.pppoe_password = new_password
            
        customer.status = request.POST.get('status', 'active')
        
        # Handle ForeignKeys (using _id allows us to assign None if empty string, or the ID directly)
        plan_id = request.POST.get('plan_id')
        customer.plan_id = plan_id if plan_id else None
        
        device_id = request.POST.get('device_id')
        customer.mikrotik_device_id = device_id if device_id else None
        
        agent_id = request.POST.get('agent_id')
        customer.agent_id = agent_id if agent_id else None
        
        barangay_id = request.POST.get('barangay_id')
        customer.barangay_id = barangay_id if barangay_id else None
        
        account_type_id = request.POST.get('account_type_id')
        customer.account_type_id = account_type_id if account_type_id else None
        
        # Cignal Play Integration
        customer.cignalplay_no = request.POST.get('cignalplay_no')
        cignal_date = request.POST.get('cignalplay_date')
        if cignal_date:
            customer.cignalplay_date = cignal_date
            
        latitude = request.POST.get('latitude')
        if latitude:
            customer.latitude = latitude
            
        longitude = request.POST.get('longitude')
        if longitude:
            customer.longitude = longitude
            
        customer.health_status = request.POST.get('health_status', 'Excellent')
        customer.health_reason = request.POST.get('health_reason')
            
        customer.save()
        messages.success(request, f'Customer {customer.full_name} updated successfully!')
        return redirect('view_customer', customer_id=customer.id)

    context = {
        'customer': customer,
        'plans': SubscriptionPlan.objects.all(),
        'devices': MikrotikDevice.objects.all(),
        'agents': Agent.objects.all(),
        'barangays': Barangay.objects.all(),
        'account_types': AccountType.objects.all()
    }
    return render(request, 'billing/edit_customer.html', context)


@login_required
def view_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    payments = customer.payments.all().order_by('-paid_at')
    
    # Try to fetch live MT connection status if they have a router
    mt_status = "Loading..."
    uptime = "Loading..."
    live_mac = "Loading..."
    last_logged_out = "Loading..."
            
    context = {
        'customer': customer,
        'payments': payments,
        'mt_status': mt_status,
        'uptime': uptime,
        'live_mac': live_mac,
        'last_logged_out': last_logged_out,
    }
    return render(request, 'billing/view_customer.html', context)


@login_required
def api_customer_mikrotik_status(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    
    data = {
        'mt_status': 'Disconnected',
        'uptime': 'N/A',
        'live_mac': customer.mac_address if customer.mac_address else 'N/A',
        'last_logged_out': 'N/A'
    }
    
    if customer.mikrotik_device and customer.pppoe_username:
        try:
            from network_manager.services import MikrotikAPI
            api = MikrotikAPI(customer.mikrotik_device)
            
            # Fetch active users
            active_users = api.get_active_pppoe_users()
            for au in active_users:
                if au.get('name') == customer.pppoe_username:
                    data['mt_status'] = "Connected"
                    data['uptime'] = au.get('uptime', 'N/A')
                    data['live_mac'] = au.get('caller-id', 'N/A')
                    break
            
            # Fetch secrets to get last-logged-out if disconnected
            secrets = api.get_ppp_secrets()
            for secret in secrets:
                if secret.get('name') == customer.pppoe_username:
                    data['last_logged_out'] = secret.get('last-logged-out', 'N/A')
                    if data['mt_status'] == "Disconnected" and not customer.mac_address:
                        data['live_mac'] = secret.get('caller-id', 'N/A')
                    break
        except Exception:
            pass
            
    from django.http import JsonResponse
    return JsonResponse(data)


@login_required
@role_required(['Admin', 'Editor'])
@permission_required('billing.delete_customer', raise_exception=True)
def delete_customer(request, customer_id):
    if request.method == 'POST':
        customer = get_object_or_404(Customer, id=customer_id)
        name = customer.full_name
        customer.delete()
        messages.success(request, f'Customer {name} deleted successfully!')
    return redirect('customer_list')

@login_required
@permission_required('billing.change_customer', raise_exception=True)
def customer_force_suspend(request, username):
    """Manually force suspends a customer (updates profile, kicks session, and updates DB status)"""
    if request.method == 'POST':
        customer = get_object_or_404(Customer, pppoe_username=username)
        if customer.mikrotik_device:
            from network_manager.services import MikrotikAPI
            api = MikrotikAPI(customer.mikrotik_device)
            success, msg = api.suspend_pppoe_user(username)
            if success:
                customer.status = 'suspended'
                customer.save()
                messages.success(request, f"Customer {username} has been forcefully suspended.")
            else:
                messages.error(request, f"Failed to suspend {username}: {msg}")
        else:
            messages.error(request, "Customer has no Mikrotik device assigned.")
        return redirect('view_customer', customer_id=customer.id)
    return redirect('customer_list')

@login_required
def customer_kick_session(request, username):
    """Manually kicks the active PPPoE session without altering their billing status"""
    if request.method == 'POST':
        customer = get_object_or_404(Customer, pppoe_username=username)
        if customer.mikrotik_device:
            from network_manager.services import MikrotikAPI
            api = MikrotikAPI(customer.mikrotik_device)
            success, msg = api.kick_active_user(username)
            if success:
                messages.success(request, f"Active session for {username} was kicked successfully.")
            else:
                messages.error(request, f"Failed to kick session for {username}: {msg}")
        else:
            messages.error(request, "Customer has no Mikrotik device assigned.")
        return redirect('view_customer', customer_id=customer.id)
    return redirect('customer_list')

@login_required
@permission_required('billing.change_customer', raise_exception=True)
def customer_force_reactivate(request, username):
    """Manually force reactivates a customer using Master Password and logs it to AuditLog"""
    if request.method == 'POST':
        import os
        admin_password = request.POST.get('admin_password', '')
        reason = request.POST.get('override_reason', '')
        customer = get_object_or_404(Customer, pppoe_username=username)
        
        # Verify that the user is a superuser and entered their correct password
        if not request.user.is_superuser or not request.user.check_password(admin_password):
            messages.error(request, "Admin Override Failed: Invalid Password or you are not a Superuser.")
            return redirect('view_customer', customer_id=customer.id)
            
        if not reason.strip():
            messages.error(request, "Admin Override Failed: Reason for override is required.")
            return redirect('view_customer', customer_id=customer.id)
            
        if customer.mikrotik_device:
            from network_manager.services import MikrotikAPI
            api = MikrotikAPI(customer.mikrotik_device)
            
            # Use their plan name as the profile, or "default" if no plan is assigned
            target_profile = customer.plan.name if customer.plan else "default"
            
            # 1. Enable User (removes bridge drop rule and enables ppp secret)
            enable_success, enable_msg = api.enable_pppoe_user(username)
            if enable_success:
                # 2. Update Profile
                prof_success, prof_msg = api.set_user_pppoe_profile(username, target_profile)
                if prof_success:
                    # 3. Kick Session (allows modem to redial and gain internet)
                    kick_success, kick_msg = api.kick_active_user(username)
                    
                    # 4. Update DB
                    customer.status = 'active'
                    # DO NOT update expiration date or outstanding balance
                    customer.save()
                    
                    # 5. Log the override in the new AuditLog model
                    from billing.models import AuditLog
                    AuditLog.objects.create(
                        admin_user=request.user if request.user.is_authenticated else None,
                        customer=customer,
                        action_type='FORCE_REACTIVATE',
                        remarks=reason
                    )
                    
                    messages.success(request, f"Customer {username} force-reactivated via Master Override.")
                else:
                    messages.error(request, f"Failed to restore profile for {username}: {prof_msg}")
            else:
                messages.error(request, f"Failed to enable user {username}: {enable_msg}")
        else:
            messages.error(request, "Customer has no Mikrotik device assigned.")
        return redirect('view_customer', customer_id=customer.id)
    return redirect('customer_list')

# ─────────────────────────────────────────────────
#  Payments
# ─────────────────────────────────────────────────


@login_required
def payment_logs_view(request):
    payments = Payment.objects.all().order_by('-paid_at')

    # Filtering
    filter_from = request.GET.get('from', '')
    filter_to = request.GET.get('to', '')
    filter_search = request.GET.get('search', '')
    filter_method = request.GET.get('method', '')

    if filter_from:
        payments = payments.filter(paid_at__gte=filter_from + ' 00:00:00')
    if filter_to:
        payments = payments.filter(paid_at__lte=filter_to + ' 23:59:59')
    if filter_search:
        payments = payments.filter(
            Q(username__icontains=filter_search)
            | Q(reference_no__icontains=filter_search)
        )
    if filter_method:
        payments = payments.filter(payment_method=filter_method)

    # Summaries
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    grand_total = Payment.objects.aggregate(t=Sum('amount'))['t'] or 0
    filtered_range_total = payments.aggregate(t=Sum('amount'))['t'] or 0

    total_today = payments.filter(
        paid_at__date=today).aggregate(t=Sum('amount'))['t'] or 0
    total_yesterday = payments.filter(
        paid_at__date=yesterday).aggregate(t=Sum('amount'))['t'] or 0

    # 14 days chart data
    chart_labels = []
    chart_values = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        chart_labels.append(d.strftime('%Y-%m-%d'))
        daily_total = payments.filter(
            paid_at__date=d).aggregate(t=Sum('amount'))['t'] or 0
        chart_values.append(float(daily_total))

    # Pagination
    per_page = int(request.GET.get('per_page', 35))
    paginator = Paginator(payments, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    methods = Payment.objects.exclude(payment_method__isnull=True).exclude(
        payment_method='').values_list('payment_method', flat=True).distinct().order_by('payment_method')

    context = {
        'page_obj': page_obj,
        'filter_from': filter_from,
        'filter_to': filter_to,
        'filter_search': filter_search,
        'filter_method': filter_method,
        'methods': methods,

        'grand_total': grand_total,
        'filtered_range_total': filtered_range_total,
        'total_today': total_today,
        'total_yesterday': total_yesterday,

        'chart_labels_js': json.dumps(chart_labels),
        'chart_values_js': json.dumps(chart_values),
    }

    return render(request, 'billing/payment_logs.html', context)


@login_required
def create_payment_view(request, customer_id):
    from django.shortcuts import get_object_or_404
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        reference_no = request.POST.get('reference_no')
        payment_date_received = request.POST.get('payment_date_received')
        reason = request.POST.get('reason')

        # Calculate days paid
        try:
            # Simple handling if provided in YYYY-MM-DDTHH:MM:SS format
            sd = datetime.fromisoformat(start_date.replace(
                'Z', '')) if start_date else timezone.now()
            ed = datetime.fromisoformat(end_date.replace(
                'Z', '')) if end_date else timezone.now()

            # ensure aware datetime
            if timezone.is_naive(sd):
                sd = timezone.make_aware(sd)
            if timezone.is_naive(ed):
                ed = timezone.make_aware(ed)

            days_paid = round((ed - sd).total_seconds() / (24 * 3600), 4)
        except Exception as e:
            print("Date parse err:", e)
            days_paid = 0
            ed = timezone.now()

        try:
            pdr = datetime.fromisoformat(
                payment_date_received.replace('Z', ''))
            if timezone.is_naive(pdr):
                pdr = timezone.make_aware(pdr)
        except Exception:
            pdr = timezone.now()

        Payment.objects.create(
            customer=customer,
            username=customer.pppoe_username or customer.full_name,
            plan_name=customer.plan.name if customer.plan else '',
            mikrotik_device_name=customer.mikrotik_device.device_name if customer.mikrotik_device else '',
            amount=amount,
            days_paid=days_paid,
            payment_method=payment_method,
            reference_no=reference_no,
            reason=reason,
            expires_at=ed,
            payment_date_received=pdr,
            paid_at=timezone.now(),
            adjusted_by=request.user.username if request.user.is_authenticated else 'system'
        )

        customer.expires_at = ed
        
        # If the customer was previously inactive or suspended, auto-reactivate them
        if customer.status in ['expired', 'suspended', 'inactive', 'past_due']:
            customer.status = 'active'
            
        customer.save()

        messages.success(
            request, f"Payment for {customer.pppoe_username or customer.full_name} processed successfully.")
        return redirect('payment_logs')

    return render(request, 'billing/pay.html', {'customer': customer})


# ─────────────────────────────────────────────────
#  Core UI & Placeholders
# ─────────────────────────────────────────────────

@login_required
def profile_view(request):
    return render(request, 'billing/profile.html')



@login_required
def settings_view(request):
    return render(request, 'billing/settings.html')

@role_required(['Admin'])
@login_required
def admin_panel_view(request):
    user_role = getattr(request.user, 'role', 'Viewer')
    if user_role != 'Admin':
        messages.error(request, "Access denied. Only Admins can access the Admin Panel.")
        return redirect('dashboard')
        
    return render(request, 'billing/admin_panel.html')


@login_required
def geomap_view(request):
    if hasattr(request.user, 'role') and request.user.role == 'Agent':
        return redirect('customer_list')
        
    # Fetch NAP boxes
    napboxes = list(NapBox.objects.values('id', 'napbox_no', 'latitude', 'longitude', 'marker_color'))
    
    # Rename keys to match the JS expected by the original template
    # Original template expects nap_latitude and nap_longitude
    for nap in napboxes:
        nap['nap_latitude'] = nap.pop('latitude')
        nap['nap_longitude'] = nap.pop('longitude')

    # Fetch Customers with lat/lng
    customers_qs = Customer.objects.filter(latitude__isnull=False, longitude__isnull=False)
    customers = []
    
    now = timezone.now()
    
    for c in customers_qs:
        # Determine status. If expires_at is in the future, it's connected (active).
        is_connected = 1 if (c.status == 'active' and (not c.expires_at or c.expires_at > now)) else 0
        customers.append({
            'id': c.id,
            'full_name': c.full_name,
            'username': c.pppoe_username or c.full_name,
            'latitude': c.latitude,
            'longitude': c.longitude,
            'is_connected': is_connected,
        })
        
    context = {
        'napboxesJson': json.dumps(napboxes, default=str),
        'customersJson': json.dumps(customers, default=str),
    }
    return render(request, 'billing/geomap.html', context)


@login_required
def save_marker_positions(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # data is a list of changes
            for item in data:
                item_type = item.get('type')
                item_id = item.get('id')
                lat = item.get('lat')
                lng = item.get('lng')
                
                if item_type == 'nap':
                    try:
                        nap = NapBox.objects.get(id=item_id)
                        nap.latitude = lat
                        nap.longitude = lng
                        nap.save()
                    except NapBox.DoesNotExist:
                        pass
                elif item_type == 'customer':
                    try:
                        customer = Customer.objects.get(id=item_id)
                        customer.latitude = lat
                        customer.longitude = lng

                        customer.save()
                    except Customer.DoesNotExist:
                        pass
                        
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
            
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)


@login_required
def rebates_logs_view(request):
    from .models import Rebate
    rebates = Rebate.objects.all().order_by('-paid_at')

    search = request.GET.get('search', '').strip()
    if search:
        rebates = rebates.filter(
            Q(username__icontains=search) |
            Q(plan_name__icontains=search) |
            Q(adjusted_by__icontains=search) |
            Q(note__icontains=search)
        )

    context = {
        'rebates': rebates,
        'search': search,
    }
    return render(request, 'billing/rebates_logs.html', context)


@login_required
def system_logs_view(request):
    logs = SystemLog.objects.all()

    # Search filter
    search_query = request.GET.get('search', '').strip()
    if search_query:
        logs = logs.filter(
            Q(table_name__icontains=search_query) |
            Q(changed_by__icontains=search_query) |
            Q(action__icontains=search_query) |
            Q(old_data__icontains=search_query) |
            Q(new_data__icontains=search_query)
        )

    # Action filter
    action_filter = request.GET.get('action_filter', '').strip().upper()
    if action_filter == 'ADD':
        logs = logs.filter(action__iexact='ADD')
    elif action_filter == 'UPDATE':
        logs = logs.filter(action__iexact='UPDATE')
    elif action_filter == 'DELETE':
        logs = logs.filter(action__iexact='DELETE')

    # Date filter
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    if date_from:
        logs = logs.filter(changed_at__gte=f"{date_from} 00:00:00")
    if date_to:
        logs = logs.filter(changed_at__lte=f"{date_to} 23:59:59")

    # Sorting
    sort_column = request.GET.get('sort', 'changed_at')
    sort_dir = request.GET.get('dir', 'desc').lower()
    
    allowed_sort_columns = ['changed_at', 'table_name', 'record_id', 'action', 'changed_by']
    if sort_column not in allowed_sort_columns:
        sort_column = 'changed_at'
        
    order_prefix = '-' if sort_dir == 'desc' else ''
    logs = logs.order_by(f"{order_prefix}{sort_column}")

    # Pagination
    paginator = Paginator(logs, 10)  # 10 logs per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Reconstruct query string for pagination links
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    
    context = {
        'logs': page_obj,
        'search': search_query,
        'action_filter': action_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort_column,
        'dir': sort_dir,
        'query_params': query_params.urlencode()
    }
    return render(request, 'billing/logs.html', context)


@login_required
def mac_history_view(request):
    from .models import CustomerMacHistory
    history = CustomerMacHistory.objects.select_related('customer').all()
    search = request.GET.get('search', '').strip()
    if search:
        history = history.filter(
            Q(customer__full_name__icontains=search) |
            Q(mac_address__icontains=search) |
            Q(customer__id__icontains=search)
        )
    return render(request, 'billing/mac_history.html', {'history': history})
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.utils import timezone
from .models import Customer
from datetime import datetime

@login_required
@permission_required('billing.add_rebate', raise_exception=True)
def customer_rebate_view(request, username):
    # Depending on how Antigravity named your field, it might be 'username' or 'pppoe_username'
    customer = get_object_or_404(Customer, pppoe_username=username) 

    if request.method == 'POST':
        new_expiry_str = request.POST.get('new_due_date_time')
        note = request.POST.get('note')
        
        if new_expiry_str:
            # Convert HTML datetime-local string to timezone-aware Python datetime
            new_expiry = timezone.datetime.fromisoformat(new_expiry_str)
            if timezone.is_naive(new_expiry):
                new_expiry = timezone.make_aware(new_expiry)

            old_expiry = customer.expires_at

            # 1. Update Customer Expiry
            customer.expires_at = new_expiry
            # customer.sms_sent_at = None  # TODO: Uncomment when SMS is added
            customer.save()

            # 2. Log the Rebate
            from .models import Rebate
            Rebate.objects.create(
                customer=customer,
                username=customer.pppoe_username,
                plan_name=customer.plan.name if customer.plan else None,
                current_expiry=old_expiry,
                expires_at=new_expiry,
                note=note,
                adjusted_by=request.user.username
            )

            # 3. TODO: Sprint 4 - Call Mikrotik API to update PPPoE comment/disconnect
            
            # 4. Pass data to success page for copying
            context = {
                'customer': customer,
                'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S'),
                'adjusted_by': request.user.username,
                'action_type': 'Rebate',
                'amount': '0.00'
            }
            return render(request, 'billing/payment_success.html', context)

    context = {
        'customer': customer,
        'current_expiry_js': customer.expires_at.strftime('%Y-%m-%dT%H:%M:%S') if customer.expires_at else timezone.now().strftime('%Y-%m-%dT%H:%M:%S')
    }
    return render(request, 'billing/customer_rebate.html', context)

@login_required
@permission_required('billing.add_rollback', raise_exception=True)
def customer_rollback_view(request, username):
    customer = get_object_or_404(Customer, pppoe_username=username)

    if request.method == 'POST':
        rollback_to_str = request.POST.get('rollback_to')
        note = request.POST.get('note')
        
        if rollback_to_str:
            new_expiry = timezone.datetime.fromisoformat(rollback_to_str)
            if timezone.is_naive(new_expiry):
                new_expiry = timezone.make_aware(new_expiry)

            old_expiry = customer.expires_at

            # 1. Update Customer Expiry (Rollback)
            customer.expires_at = new_expiry
            customer.save()

            # 2. Log the Rollback
            from .models import Rebate
            Rebate.objects.create(
                customer=customer,
                username=customer.pppoe_username,
                plan_name=customer.plan.name if customer.plan else None,
                current_expiry=old_expiry,
                expires_at=new_expiry,
                note=f"Rollback: {note}",
                adjusted_by=request.user.username
            )

            # 3. TODO: Sprint 4 - Mikrotik API Sync

            context = {
                'customer': customer,
                'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S'),
                'adjusted_by': request.user.username,
                'action_type': 'Rollback Expiry',
                'amount': '0.00'
            }
            return render(request, 'billing/payment_success.html', context)

    context = {
        'customer': customer,
        'current_expiry_js': customer.expires_at.strftime('%Y-%m-%dT%H:%M') if customer.expires_at else ''
    }
    return render(request, 'billing/customer_rollback.html', context)

@login_required
def payment_success_view(request):
    """Fallback view if someone accesses the URL directly"""
    return redirect('customer_list')

@login_required
def payment_addon_logs_view(request):
    """
    Replicates the legacy 'payment_addon_logs.php' view showing
    customers and their current plan status.
    """
    customers = Customer.objects.select_related('plan').all().order_by('-created_at')
    
    # Calculate simple stats
    now = timezone.now()
    active_count = customers.filter(expires_at__gte=now).count()
    expired_count = customers.filter(expires_at__lt=now).count()
    no_plan_count = customers.filter(plan__isnull=True).count()

    context = {
        'customers': customers,
        'active_count': active_count,
        'expired_count': expired_count,
        'no_plan_count': no_plan_count,
    }
    return render(request, 'billing/payment_addon_logs.html', context)

@login_required
def payment_portal_view(request):
    """A centralized dashboard for cashiers to search and select a customer to pay."""
    customers = Customer.objects.select_related('plan').all().order_by('-created_at')
    return render(request, 'billing/payment_portal.html', {'customers': customers})

@login_required
@permission_required('billing.add_payment', raise_exception=True)
def pay_customer_view(request, username):
    customer = get_object_or_404(Customer, pppoe_username=username)
    
    # Calculate Monthly Price
    monthly_price = float(customer.plan.price) if customer.plan else 0.0

    # Capture dynamic redirect URL
    next_url = request.GET.get('next') or request.POST.get('next_url') or request.META.get('HTTP_REFERER') or reverse('payment_portal')

    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        reference_no = request.POST.get('reference_no', '')
        reason = request.POST.get('reason', '')
        
        if amount:
            from decimal import Decimal
            amount_float = float(amount)
            
            # Determine baseline current expiration
            if start_date_str:
                current_exp = timezone.datetime.fromisoformat(start_date_str.replace('Z', ''))
                if timezone.is_naive(current_exp):
                    current_exp = timezone.make_aware(current_exp)
            elif customer.expires_at and customer.expires_at > timezone.now():
                current_exp = customer.expires_at
            else:
                current_exp = timezone.now()

            # Calculate new expiration using the staggered logic
            new_expiry = calculate_new_expiration_date(current_exp, amount_float, monthly_price)

            with transaction.atomic():
                # Lock the customer row for atomic update
                locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)
                was_suspended = locked_customer.status in ['suspended', 'inactive', 'expired']
                
                # 1. Update Customer Expiry
                locked_customer.expires_at = new_expiry
                
                # 2. Deduct from outstanding balance
                locked_customer.outstanding_balance -= Decimal(amount)
                
                # 3. Update Status if suspended
                if was_suspended:
                    locked_customer.status = 'active'
                
                locked_customer.save()

                # 4. Log the Payment
                Payment.objects.create(
                    customer=locked_customer,
                    username=locked_customer.pppoe_username,
                    plan_name=locked_customer.plan.name if locked_customer.plan else None,
                    amount=amount, 
                    payment_method=payment_method, 
                    reference_no=reference_no, 
                    reason=reason, 
                    expires_at=new_expiry,
                    adjusted_by=request.user.username
                )

            # 5. Mikrotik API Reactivation & Comments
            if customer.mikrotik_device:
                try:
                    from network_manager.services import MikrotikAPI
                    api = MikrotikAPI(customer.mikrotik_device)
                    
                    # Push Payment Comment
                    comment_text = f"Paid {amount} PHP on {timezone.now().strftime('%b %d, %Y')}. Expires: {new_expiry.strftime('%b %d, %Y')}"
                    api.set_pppoe_comment(customer.pppoe_username, comment_text)
                    
                    if was_suspended and customer.plan and customer.plan.name:
                        # 1. Enable the user (Removes bridge drop and enables secret)
                        api.enable_pppoe_user(customer.pppoe_username)
                        # 2. Update the profile back to their plan
                        api.set_user_pppoe_profile(customer.pppoe_username, customer.plan.name)
                        # 3. Kick them so they reconnect and get the new profile
                        api.kick_active_user(customer.pppoe_username)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to sync renewal for {customer.pppoe_username} on MikroTik: {e}")

            # 4. Success Output
            context = {
                'customer': customer,
                'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S'),
                'adjusted_by': request.user.username,
                'action_type': 'Standard Renewal',
                'amount': amount,
                'next_url': next_url,
            }
            return render(request, 'billing/payment_success.html', context)

    # GET Request: Setup defaults
    current_expiry = customer.expires_at or timezone.now()
    start_default_str = current_expiry.strftime('%Y-%m-%dT%H:%M:%S')
    
    # Add roughly one month for the default end date
    end_default = current_expiry + timezone.timedelta(days=30)
    end_default_str = end_default.strftime('%Y-%m-%dT%H:%M:%S')

    context = {
        'customer': customer,
        'current_expiry_display': current_expiry.strftime('%Y-%m-%d %H:%M:%S'),
        'start_default_str': start_default_str,
        'end_default_str': end_default_str,
        'monthly_price': monthly_price,
        'next_url': next_url,
    }
    return render(request, 'billing/pay_customer.html', context)

# ==========================================
# MASTER DATA MANAGEMENT (Settings)
# ==========================================
from .models import AccountType, Barangay
from .forms import AccountTypeForm, BarangayForm

@login_required
def account_type_list(request):
    account_types = AccountType.objects.all().order_by('type_name')
    return render(request, 'billing/settings_list.html', {
        'items': account_types,
        'title': 'Manage Account Types',
        'item_name': 'Account Type',
        'create_url': 'create_account_type',
        'edit_url_name': 'edit_account_type',
        'delete_url_name': 'delete_account_type',
    })

@login_required
def create_account_type(request):
    if request.method == 'POST':
        form = AccountTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account Type created successfully!")
            return redirect('account_type_list')
    else:
        form = AccountTypeForm()
    return render(request, 'billing/settings_form.html', {'form': form, 'title': 'Create Account Type', 'back_url': 'account_type_list'})

@role_required(['Admin', 'Editor'])
@login_required
def edit_account_type(request, pk):
    obj = get_object_or_404(AccountType, pk=pk)
    if request.method == 'POST':
        form = AccountTypeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Account Type updated successfully!")
            return redirect('account_type_list')
    else:
        form = AccountTypeForm(instance=obj)
    return render(request, 'billing/settings_form.html', {'form': form, 'title': 'Edit Account Type', 'back_url': 'account_type_list'})

@role_required(['Admin', 'Editor'])
@login_required
def delete_account_type(request, pk):
    obj = get_object_or_404(AccountType, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, "Account Type deleted successfully!")
    return redirect('account_type_list')


@login_required
def barangay_list(request):
    barangays = Barangay.objects.all().order_by('name')
    return render(request, 'billing/settings_list.html', {
        'items': barangays,
        'title': 'Manage Barangays',
        'item_name': 'Barangay',
        'create_url': 'create_barangay',
        'edit_url_name': 'edit_barangay',
        'delete_url_name': 'delete_barangay',
    })

@login_required
def create_barangay(request):
    if request.method == 'POST':
        form = BarangayForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Barangay created successfully!")
            return redirect('barangay_list')
    else:
        form = BarangayForm()
    return render(request, 'billing/settings_form.html', {'form': form, 'title': 'Create Barangay', 'back_url': 'barangay_list'})

@login_required
def edit_barangay(request, pk):
    obj = get_object_or_404(Barangay, pk=pk)
    if request.method == 'POST':
        form = BarangayForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Barangay updated successfully!")
            return redirect('barangay_list')
    else:
        form = BarangayForm(instance=obj)
    return render(request, 'billing/settings_form.html', {'form': form, 'title': 'Edit Barangay', 'back_url': 'barangay_list'})

@login_required
def delete_barangay(request, pk):
    obj = get_object_or_404(Barangay, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, "Barangay deleted successfully!")
    return redirect('barangay_list')

@login_required
@role_required(['Admin', 'Editor'])
def send_semaphore_sms(phone, message):
    api_key = 'a1be64e85146a946d40aeb1677d37a48'
    url = 'https://api.semaphore.co/api/v4/messages'
    payload = {
        'apikey': api_key,
        'number': phone,
        'message': message,
        'sendername': 'SEMAPHORE'
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        return response.text, response.status_code == 200
    except Exception as e:
        return str(e), False

@login_required
def sms_view(request):
    if request.method == 'POST':
        if 'send_sms_custom' in request.POST:
            phone = request.POST.get('phone')
            message = request.POST.get('message')
            
            response_text, is_success = send_semaphore_sms(phone, message)
            status = 'success' if is_success else 'error'
            
            SmsLog.objects.create(
                phone=phone,
                message=message,
                response=response_text,
                status=status
            )
            messages.info(request, f"SMS sent to {phone}. Response: {response_text}")
            
        elif 'bulk_send_sms' in request.POST:
            phones_str = request.POST.get('selected_phones', '')
            bulk_message = request.POST.get('bulk_message')
            phones = [p.strip() for p in phones_str.split(',') if p.strip()]
            
            for phone in phones:
                response_text, is_success = send_semaphore_sms(phone, bulk_message)
                status = 'success' if is_success else 'error'
                SmsLog.objects.create(
                    phone=phone,
                    message=bulk_message,
                    response=response_text,
                    status=status
                )
            messages.info(request, f"Bulk SMS sent to {len(phones)} recipients.")
            
        return redirect('sms_messaging')

    search = request.GET.get('search', '')
    customers = Customer.objects.exclude(username__isnull=True).exclude(username='')
    
    if search:
        customers = customers.filter(
            Q(username__icontains=search) |
            Q(full_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(address__icontains=search) |
            Q(status__icontains=search)
        )
    
    customers = customers.order_by('full_name')
    paginator = Paginator(customers, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    sms_logs = SmsLog.objects.all()[:100]
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'sms_logs': sms_logs
    }
    return render(request, 'billing/sms_messaging.html', context)

@login_required
def auto_suspend_view(request):
    if request.method == 'POST':
        usernames = request.POST.getlist('usernames')
        if not usernames:
            messages.error(request, 'No users selected for suspension.')
            return redirect('auto_suspend')
            
        suspended_count = 0
        errors = []
        
        # Group by device to minimize connections
        customers_to_suspend = Customer.objects.filter(username__in=usernames).select_related('mikrotik_device')
        device_users = {}
        for c in customers_to_suspend:
            if c.mikrotik_device:
                if c.mikrotik_device not in device_users:
                    device_users[c.mikrotik_device] = []
                device_users[c.mikrotik_device].append(c)
                
        for device, users in device_users.items():
            api = MikrotikAPI(device)
            for user in users:
                success, msg = api.suspend_pppoe_user(user.username)
                if success:
                    suspended_count += 1
                else:
                    errors.append(f"Failed to suspend {user.username}: {msg}")
                    
        if suspended_count > 0:
            messages.success(request, f'Successfully suspended {suspended_count} users.')
        if errors:
            for err in errors:
                messages.error(request, err)
                
        return redirect('auto_suspend')

    # GET request: fetch past due customers
    past_due_customers = Customer.objects.filter(
        expires_at__lte=timezone.now(),
        mikrotik_device__isnull=False
    ).exclude(username__isnull=True).exclude(username='').select_related('mikrotik_device')

    display_customers = []
    
    # Group by device for efficient querying
    device_customers = {}
    for c in past_due_customers:
        if c.mikrotik_device not in device_customers:
            device_customers[c.mikrotik_device] = []
        device_customers[c.mikrotik_device].append(c)
        
    for device, customers in device_customers.items():
        api = MikrotikAPI(device)
        secrets = api.get_ppp_secrets()
        
        # Build lookup dict
        secret_dict = {s.get('name'): s.get('profile', 'N/A') for s in secrets}
        
        for c in customers:
            profile = secret_dict.get(c.username, 'Not Found')
            if str(profile).lower() != 'expired':
                c.mikrotik_profile = profile
                display_customers.append(c)

    display_customers.sort(key=lambda x: x.full_name)
    
    context = {
        'due_customers': display_customers
    }
    return render(request, 'billing/auto_suspend.html', context)


@login_required
def cignal_play_list_view(request):
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    
    customers = Customer.objects.exclude(cignalplay_no__isnull=True).exclude(cignalplay_no__exact='')

    if search:
        customers = customers.filter(
            Q(full_name__icontains=search) |
            Q(username__icontains=search) |
            Q(cignalplay_no__icontains=search) |
            Q(cignalplay_adjustedby__icontains=search)
        )
        
    customers = customers.order_by('-created_at')
    
    # We will pass this to template and handle basic status filtering in Python if needed, 
    # but for now let's just pass the raw customers.
    paginator = Paginator(customers, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
    }
    return render(request, 'billing/cignal_play_list.html', context)


@login_required
def add_on_payments_view(request):
    search = request.GET.get('search', '')
    
    # Very similar to cignal_play_list but might show all with add-on plans in CignalPlay table
    customers_with_addons = Customer.objects.filter(cignal_plans__isnull=False).distinct()

    if search:
        customers_with_addons = customers_with_addons.filter(
            Q(full_name__icontains=search) |
            Q(username__icontains=search) |
            Q(cignalplay_no__icontains=search)
        )
        
    customers_with_addons = customers_with_addons.order_by('-created_at')
    
    paginator = Paginator(customers_with_addons, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'billing/add_on_payments.html', context)


@login_required
def cignalplay_form_view(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        plan_name = request.POST.get('plan_name')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        adjusted_by = request.POST.get('adjusted_by')
        
        CignalPlay.objects.create(
            customer=customer,
            plan_name=plan_name,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            adjusted_by=adjusted_by
        )
        
        # Also update the customer's cignalplay_adjustedby field
        customer.cignalplay_adjustedby = adjusted_by
        customer.save()
        
        messages.success(request, f"Successfully recorded Cignal Play / Add-on payment for {customer.full_name}.")
        return redirect('user_cignal_logs', customer_id=customer.id)
        
    context = {
        'customer': customer
    }
    return render(request, 'billing/cignalplay_form.html', context)


@login_required
def user_cignal_logs_view(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    logs = customer.cignal_plans.all()
    
    context = {
        'customer': customer,
        'logs': logs
    }
    return render(request, 'billing/user_cignal_logs.html', context)


@login_required
def statement_of_account_view(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    payments = customer.payments.all().order_by('-paid_at')
    
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    
    if date_from and date_to:
        payments = payments.filter(paid_at__date__gte=date_from, paid_at__date__lte=date_to)
        
    total_paid = sum(p.amount for p in payments)
    
    context = {
        'customer': customer,
        'payments': payments,
        'date_from': date_from,
        'date_to': date_to,
        'total_paid': total_paid,
        'current_date': timezone.now()
    }
    return render(request, 'billing/statement_of_account.html', context)


@login_required
def backup_database_view(request):
    db_path = settings.DATABASES['default']['NAME']
    if os.path.exists(db_path):
        response = FileResponse(open(db_path, 'rb'), as_attachment=True, filename=f"gametech_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.sqlite3")
        return response
    
    messages.error(request, "Database file not found.")
    return redirect('settings')

from django.contrib.auth import authenticate, login

def unified_login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.session.get('customer_id'):
        return redirect('customer_portal:portal_dashboard')

    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        # 1. Try standard Admin/Staff login
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url if next_url else 'dashboard')
            
        # 2. Try Customer Login
        try:
            customer = Customer.objects.get(pppoe_username=u, pppoe_password=p)
            request.session['customer_id'] = customer.id
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url if next_url else 'customer_portal:portal_dashboard')
        except Customer.DoesNotExist:
            messages.error(request, 'Invalid username or password.')
            
    return render(request, 'billing/login.html')
