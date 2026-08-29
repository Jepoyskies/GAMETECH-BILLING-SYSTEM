from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from .decorators import role_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, Max
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime

from .models import (
    SystemAdmin, SubscriptionPlan, Agent, AccountType,
    Customer, Barangay, Payment, Rebate, SystemLog, SmsLog, CignalPlay, AuditLog, AddOnRequest, Notification
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

    # Totals
    yesterday = today - timedelta(days=1)
    start_of_week = today - timedelta(days=today.weekday())
    
    payments = Payment.objects.all()
    
    total_today = payments.filter(created_at__date=today).aggregate(t=Sum('amount'))['t'] or 0
    total_yesterday = payments.filter(created_at__date=yesterday).aggregate(t=Sum('amount'))['t'] or 0
    total_week = payments.filter(created_at__date__gte=start_of_week).aggregate(t=Sum('amount'))['t'] or 0
    total_month = payments.filter(created_at__month=today.month, created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0
    total_year = payments.filter(created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0

    totals = {
        'today': f"{total_today:,.2f}",
        'yesterday': f"{total_yesterday:,.2f}",
        'week': f"{total_week:,.2f}",
        'month': f"{total_month:,.2f}",
        'year': f"{total_year:,.2f}",
    }

    # Revenue Growth
    last_month_dt = today.replace(day=1) - timedelta(days=1)
    total_last_month = payments.filter(created_at__month=last_month_dt.month, created_at__year=last_month_dt.year).aggregate(t=Sum('amount'))['t'] or 0
    
    if total_last_month > 0:
        growth_percent = ((float(total_month) - float(total_last_month)) / float(total_last_month)) * 100
    else:
        growth_percent = 100.0 if total_month > 0 else 0.0

    growth_icon = 'fa-arrow-up' if growth_percent >= 0 else 'fa-arrow-down'
    growth_color = 'text-success' if growth_percent >= 0 else 'text-danger'

    # Collection Rate
    distinct_payers_this_month = payments.filter(created_at__month=today.month, created_at__year=today.year).values('customer').distinct().count()
    collection_rate = (distinct_payers_this_month / total_customers * 100) if total_customers > 0 else 0

    # Sales by Month Chart
    months_js = []
    sales_by_month_js = []
    for i in range(11, -1, -1):
        m = (today.month - 1 - i) % 12 + 1
        y = today.year + ((today.month - 1 - i) // 12)
        month_name = calendar.month_abbr[m]
        months_js.append(month_name)
        m_total = payments.filter(created_at__month=m, created_at__year=y).aggregate(t=Sum('amount'))['t'] or 0
        sales_by_month_js.append(float(m_total))

    # Sales by Day (Last 7 days)
    days_js = []
    sales_by_day_js = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        days_js.append(d.strftime("%a"))
        d_total = payments.filter(created_at__date=d).aggregate(t=Sum('amount'))['t'] or 0
        sales_by_day_js.append(float(d_total))

    # Pie Chart
    cash = payments.filter(payment_method='Cash', created_at__month=today.month, created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0
    gcash = payments.filter(payment_method='GCash', created_at__month=today.month, created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0
    bank = payments.filter(payment_method='Bank Transfer', created_at__month=today.month, created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0
    
    pie_labels_js = ["Cash", "GCash", "Bank Transfer"]
    pie_data_js = [float(cash), float(gcash), float(bank)]

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

    # Top Paying Clients
    top_clients_qs = payments.values('customer__full_name', 'customer__pppoe_username').annotate(
        total_paid=Sum('amount'), last_payment=Max('created_at')
    ).order_by('-total_paid')[:5]

    top_clients = []
    for c in top_clients_qs:
        if c['customer__full_name'] or c['customer__pppoe_username']:
            top_clients.append({
                'username': c['customer__pppoe_username'] or c['customer__full_name'],
                'total_paid': c['total_paid'],
                'last_payment': c['last_payment']
            })

    # Top Service Plans
    top_plans_qs = Customer.objects.values('plan__name').annotate(
        cnt=Count('id')).order_by('-cnt')[:5]
    top_plans = [{'plan_name': p['plan__name'] or 'None',
                  'cnt': p['cnt']} for p in top_plans_qs]

    # Expiring Users (Next 3 days & recently expired)
    three_days_ahead = now + timedelta(days=3)
    expiring_qs = Customer.objects.filter(expires_at__isnull=False, expires_at__lte=three_days_ahead).order_by('-expires_at')[:5]
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
        'growth_percent': growth_percent,
        'growth_icon': growth_icon,
        'growth_color': growth_color,
        'growth_percent_formatted': f"{growth_percent:.1f}",
        'new_customers_this_month': new_customers_this_month,
        'collection_rate_formatted': f"{collection_rate:.1f}",
        'distinct_payers_this_month': distinct_payers_this_month,
        'total_customers': total_customers,
        'totals': totals,
        'recent_admin_logins': recent_admin_logins,
        'top_clients': top_clients,
        'top_plans': top_plans,
        'expiring_users': expiring_users,
        'months_js': json.dumps(months_js),
        'sales_by_month_js': json.dumps(sales_by_month_js),
        'days_js': json.dumps(days_js),
        'sales_by_day_js': json.dumps(sales_by_day_js),
        'pie_labels_js': json.dumps(pie_labels_js),
        'pie_data_js': json.dumps(pie_data_js),
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
                
                Notification.objects.create(
                    title=f"Router Status: {health_status}", 
                    message=f"Router {device.device_name} updated: {health_reason}", 
                    notification_type='network', 
                    link='/live-monitoring/'
                )
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
                    
                    Notification.objects.create(
                        title=f"Barangay Status: {health_status}", 
                        message=f"{barangay.name} updated: {health_reason}", 
                        notification_type='network', 
                        link='/live-monitoring/'
                    )
                    
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
                
                Notification.objects.create(
                    title=f"Customer Status: {health_status}", 
                    message=f"{customer.full_name} updated: {health_reason}", 
                    notification_type='network', 
                    link=f"/network/health/resolve/customer/{customer.id}/"
                )
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
    elif scope == 'addon':
        from .models import AddOnRequest
        addon = get_object_or_404(AddOnRequest, id=item_id)
        addon.status = 'Resolved'
        addon.save()
        messages.success(request, f"Resolved add-on request ({addon.addon_type}) for {addon.customer.full_name}.")
    return redirect(request.META.get('HTTP_REFERER', 'live_monitoring'))


@login_required
def live_monitoring_view(request):
    from .models import Barangay, Customer, AddOnRequest
    devices = MikrotikDevice.objects.all().order_by('device_name')
    barangays = Barangay.objects.all().order_by('name')
    customers = Customer.objects.filter(status='active').order_by('full_name')
    active_device_alerts = MikrotikDevice.objects.exclude(health_status='Excellent')
    active_barangay_alerts = Barangay.objects.exclude(health_status='Excellent')
    active_customer_alerts = Customer.objects.exclude(health_status__in=['Excellent', 'Good', 'Stable', 'Strong']).filter(status='active')
    pending_addon_requests = AddOnRequest.objects.filter(status='Pending').order_by('-requested_at')
    
    return render(request, 'billing/live_monitoring.html', {
        'devices': devices,
        'barangays': barangays,
        'customers': customers,
        'active_device_alerts': active_device_alerts,
        'active_barangay_alerts': active_barangay_alerts,
        'active_customer_alerts': active_customer_alerts,
        'pending_addon_requests': pending_addon_requests
    })


@login_required
def api_live_monitoring_data(request):
    from django.core.cache import cache
    response_data = cache.get('live_monitoring_data')
    
    # Fallback if cache is empty or expired
    if not response_data:
        response_data = {
            'users': [],
            'routers': [],
            'offline_users': [],
            'total_active_subs': 0
        }
        
    return JsonResponse(response_data)


@login_required
def api_offline_users(request):
    response_data = {'offline_users': []}
    from billing.models import Customer
    devices = MikrotikDevice.objects.all()
    for device in devices:
        try:
            api = MikrotikAPI(device)
            active_users = api.get_active_pppoe_users()
            active_mt_usernames = {au.get('name') for au in active_users if au.get('name')}
            
            active_db_customers = Customer.objects.filter(
                status='active', 
                mikrotik_device=device
            ).exclude(pppoe_username__isnull=True).exclude(pppoe_username='')
            
            offline_customer_usernames = [c.pppoe_username for c in active_db_customers if c.pppoe_username not in active_mt_usernames]
            
            if offline_customer_usernames:
                secrets = api.get_ppp_secrets()
                secrets_dict = {s.get('name'): s.get('last-logged-out', 'Unknown') for s in secrets if s.get('name')}
                
                for c in active_db_customers:
                    if c.pppoe_username in offline_customer_usernames:
                        response_data['offline_users'].append({
                            'id': c.id,
                            'full_name': c.full_name,
                            'username': c.pppoe_username,
                            'phone': c.phone,
                            'address': c.address,
                            'device_id': device.id,
                            'device_name': device.device_name,
                            'last_logged_out': secrets_dict.get(c.pppoe_username, 'Unknown')
                        })
            api.connection.disconnect()
        except Exception as e:
            print(f"Error fetching offline users for {device.device_name}: {e}")
            
    return JsonResponse(response_data)


@login_required
def api_router_uplink(request):
    routers = []
    devices = MikrotikDevice.objects.all()
    for device in devices:
        try:
            api = MikrotikAPI(device)
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
                        uplink_status = 'Unstable' if rtt_ms > 150 else 'Online'
            except Exception as e:
                uplink_status = 'Offline'
                uplink_ping = 'Error'
                
            routers.append({
                'id': device.id,
                'name': device.device_name,
                'uplink_status': uplink_status,
                'uplink_ping': uplink_ping,
            })
            api.connection.disconnect()
        except Exception as e:
            # Device unreachable or API error
            pass
            
    return JsonResponse({'routers': routers})


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
    
    q = request.GET.copy()
    if 'page' in q:
        del q['page']
    context['query_params'] = q.urlencode()

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
    # Auto-sync any Django Users (like hidden superusers created via CLI) to SystemAdmin
    from django.contrib.auth.models import User
    from django.db.models import Q
    for u in User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)):
        sys_admin, created = SystemAdmin.objects.get_or_create(
            username=u.username,
            defaults={
                'full_name': f"{u.first_name} {u.last_name}".strip() or u.username,
                'email': u.email or f"{u.username}@example.com",
                'role': 'Admin' if u.is_superuser else 'Viewer',
                'status': 'Active' if u.is_active else 'Inactive',
                'password_hash': 'managed_by_django'
            }
        )
        if not created and u.is_superuser and sys_admin.role != 'Admin':
            sys_admin.role = 'Admin'
            sys_admin.save(update_fields=['role'])

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
@require_POST
def bulk_sms_view(request):
    import json
    import time
    try:
        data = json.loads(request.body)
        customer_ids = data.get('customer_ids', [])
        message = data.get('message', '').strip()

        if not customer_ids or not message:
            return JsonResponse({'success': False, 'error': 'Missing customers or message.'})

        customers = Customer.objects.filter(id__in=customer_ids)
        sent_count = 0

        for customer in customers:
            if customer.phone:
                response, is_success = send_semaphore_sms(customer.phone, message)
                if is_success:
                    sent_count += 1
                time.sleep(0.1)  # Prevent rate limiting

        return JsonResponse({'success': True, 'sent_count': sent_count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def customer_list(request):
    from network_manager.models import MikrotikDevice
    from django.utils import timezone
    from datetime import timedelta
    
    customers = Customer.objects.select_related(
        'plan', 'agent', 'barangay', 'mikrotik_device').all()
        
    filter_type = request.GET.get('filter', 'all')
    
    if filter_type == 'nearing_expiration':
        three_days_from_now = timezone.now() + timedelta(days=3)
        customers = customers.filter(expires_at__lte=three_days_from_now, status='active')
    elif filter_type == 'advance_payment':
        customers = customers.filter(outstanding_balance__gt=0)
        
    devices = MikrotikDevice.objects.all().order_by('device_name')
    from .models import Barangay
    barangays = Barangay.objects.all().order_by('name')
    return render(request, 'billing/customer_list.html', {
        'customers': customers,
        'devices': devices,
        'barangays': barangays,
        'filter_type': filter_type
    })


@login_required
@role_required(['Admin', 'Agent', 'CSR'])
@permission_required('billing.add_customer', raise_exception=True)
def add_customer(request):
    if request.method == 'POST':
        from django.utils.crypto import get_random_string
        if request.user.role == 'Agent':
            barangay_name = request.POST.get('barangay_name')
            if barangay_name:
                barangay, _ = Barangay.objects.get_or_create(
                    name__iexact=barangay_name, 
                    defaults={'name': barangay_name, 'health_status': 'Excellent'}
                )
                barangay_id = barangay.id
            else:
                barangay_id = None
            latitude = None
            longitude = None
        else:
            barangay_id = request.POST.get('barangay_id')
            latitude = request.POST.get('latitude') or None
            longitude = request.POST.get('longitude') or None

        customer = Customer.objects.create(
            full_name=request.POST.get('full_name'),
            email=request.POST.get('email') or None,
            phone=request.POST.get('phone'),
            address=request.POST.get('address'),
            pppoe_username=request.POST.get('pppoe_username') or None,
            pppoe_password=request.POST.get('pppoe_password') or get_random_string(8),
            status='pending' if request.user.role == 'Agent' else request.POST.get('status', 'active'),
            plan_id=request.POST.get('plan_id'),
            mikrotik_device_id=request.POST.get('device_id') or None,
            agent_id=request.POST.get('agent_id'),
            barangay_id=barangay_id,
            account_type_id=request.POST.get('account_type_id') or None,
            latitude=latitude,
            longitude=longitude,
            cignalplay_no=request.POST.get('cignalplay_no'),
            cignalplay_date=request.POST.get('cignalplay_date') or None,
            created_form_by=request.user.username
        )
        
        from .models import SystemLog
        SystemLog.objects.create(
            table_name='Customer',
            record_id=str(customer.id),
            action='ADD',
            changed_by=request.user.username,
            target_name=customer.full_name,
            old_data="",
            new_data=f"Name: {customer.full_name}\nPhone: {customer.phone}\nStatus: {customer.status}"
        )
        messages.success(request, 'Customer added successfully!')
        return redirect('customer_list')
    context = {
        'plans': SubscriptionPlan.objects.all().order_by('price'),
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
        old_data = []
        new_data = []

        def check_change(field_name, old_val, new_val):
            # Treat None and empty string as equivalent for logging
            if (old_val or "") != (new_val or ""):
                old_data.append(f"{field_name}: {old_val}")
                new_data.append(f"{field_name}: {new_val}")

        check_change('Name', customer.full_name, request.POST.get('full_name'))
        customer.full_name = request.POST.get('full_name')

        check_change('Email', customer.email, request.POST.get('email'))
        customer.email = request.POST.get('email') or None

        check_change('Phone', customer.phone, request.POST.get('phone'))
        customer.phone = request.POST.get('phone')

        check_change('Address', customer.address, request.POST.get('address'))
        customer.address = request.POST.get('address')

        check_change('PPPoE Username', customer.pppoe_username, request.POST.get('pppoe_username'))
        customer.pppoe_username = request.POST.get('pppoe_username') or None
        
        new_password = request.POST.get('pppoe_password')
        if new_password:
            check_change('PPPoE Password', '***', '*** (changed)')
            customer.pppoe_password = new_password
        elif not customer.pppoe_password:
            from django.utils.crypto import get_random_string
            customer.pppoe_password = get_random_string(8)
            check_change('PPPoE Password', 'None', '*** (auto-generated)')
            
        check_change('Status', customer.status, request.POST.get('status', 'active'))
        customer.status = request.POST.get('status', 'active')
        
        # Handle ForeignKeys (using _id allows us to assign None if empty string, or the ID directly)
        plan_id = request.POST.get('plan_id')
        if str(customer.plan_id or "") != str(plan_id or ""):
            old_data.append(f"Plan ID: {customer.plan_id}")
            new_data.append(f"Plan ID: {plan_id}")
        customer.plan_id = plan_id if plan_id else None
        
        device_id = request.POST.get('device_id')
        if str(customer.mikrotik_device_id or "") != str(device_id or ""):
            old_data.append(f"Device ID: {customer.mikrotik_device_id}")
            new_data.append(f"Device ID: {device_id}")
        customer.mikrotik_device_id = device_id if device_id else None
        
        agent_id = request.POST.get('agent_id')
        if str(customer.agent_id or "") != str(agent_id or ""):
            old_data.append(f"Agent ID: {customer.agent_id}")
            new_data.append(f"Agent ID: {agent_id}")
        customer.agent_id = agent_id if agent_id else None
        
        if request.user.role == 'Agent':
            barangay_name = request.POST.get('barangay_name')
            if barangay_name:
                barangay, _ = Barangay.objects.get_or_create(
                    name__iexact=barangay_name, 
                    defaults={'name': barangay_name, 'health_status': 'Excellent'}
                )
                if str(customer.barangay_id or "") != str(barangay.id):
                    old_data.append(f"Barangay ID: {customer.barangay_id}")
                    new_data.append(f"Barangay ID: {barangay.id}")
                customer.barangay_id = barangay.id
            else:
                if customer.barangay_id is not None:
                    old_data.append(f"Barangay ID: {customer.barangay_id}")
                    new_data.append(f"Barangay ID: None")
                customer.barangay_id = None
        else:
            barangay_id = request.POST.get('barangay_id')
            if str(customer.barangay_id or "") != str(barangay_id or ""):
                old_data.append(f"Barangay ID: {customer.barangay_id}")
                new_data.append(f"Barangay ID: {barangay_id}")
            customer.barangay_id = barangay_id if barangay_id else None
        
        account_type_id = request.POST.get('account_type_id')
        if str(customer.account_type_id or "") != str(account_type_id or ""):
            old_data.append(f"Account Type ID: {customer.account_type_id}")
            new_data.append(f"Account Type ID: {account_type_id}")
        customer.account_type_id = account_type_id if account_type_id else None
        
        if request.user.role != 'Agent':
            latitude = request.POST.get('latitude')
            if latitude:
                check_change('Latitude', customer.latitude, latitude)
                customer.latitude = latitude
            longitude = request.POST.get('longitude')
            if longitude:
                check_change('Longitude', customer.longitude, longitude)
                customer.longitude = longitude
        
        # Cignal Play Integration
        check_change('Cignal Play No', customer.cignalplay_no, request.POST.get('cignalplay_no'))
        customer.cignalplay_no = request.POST.get('cignalplay_no')
        
        cignal_date = request.POST.get('cignalplay_date')
        if cignal_date:
            check_change('Cignal Play Date', str(customer.cignalplay_date) if customer.cignalplay_date else None, cignal_date)
            customer.cignalplay_date = cignal_date
            
        check_change('Health Status', customer.health_status, request.POST.get('health_status', 'Excellent'))
        customer.health_status = request.POST.get('health_status', 'Excellent')

        check_change('Health Reason', customer.health_reason, request.POST.get('health_reason'))
        customer.health_reason = request.POST.get('health_reason')
            
        if old_data or new_data:
            from .models import SystemLog
            SystemLog.objects.create(
                table_name='Customer',
                record_id=str(customer.id),
                action='UPDATE',
                changed_by=request.user.username,
                target_name=customer.full_name,
                old_data='\n'.join(old_data),
                new_data='\n'.join(new_data)
            )

        customer.save()
        messages.success(request, f'Customer {customer.full_name} updated successfully!')
        return redirect('view_customer', customer_id=customer.id)

    context = {
        'customer': customer,
        'plans': SubscriptionPlan.objects.all().order_by('price'),
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
@role_required(['Admin'])
def edit_customer_expiration(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        new_date_str = request.POST.get('expires_at')
        if new_date_str:
            from django.utils.dateparse import parse_datetime
            from .models import SystemLog
            new_date = parse_datetime(new_date_str)
            if new_date:
                old_date = customer.expires_at.strftime("%Y-%m-%d %H:%M:%S") if customer.expires_at else "None"
                customer.expires_at = new_date
                customer.save()
                SystemLog.objects.create(
                    table_name='Customer',
                    record_id=str(customer.id),
                    action='UPDATE',
                    changed_by=request.user.username,
                    old_data=f"Expiration: {old_date}",
                    new_data=f"Expiration: {new_date.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                messages.success(request, f"Expiration date for {customer.full_name} has been successfully updated.")
            else:
                messages.error(request, "Invalid date format.")
    return redirect('view_customer', customer_id=customer.id)


@login_required
@role_required(['Admin'])
def edit_customer_balance(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        new_balance_str = request.POST.get('outstanding_balance')
        if new_balance_str is not None:
            try:
                from decimal import Decimal
                from .models import SystemLog
                new_balance = Decimal(new_balance_str)
                old_balance = customer.outstanding_balance
                customer.outstanding_balance = new_balance
                customer.save()
                SystemLog.objects.create(
                    table_name='Customer',
                    record_id=str(customer.id),
                    action='UPDATE',
                    changed_by=request.user.username,
                    target_name=customer.full_name,
                    old_data=f"Balance: ₱{old_balance}",
                    new_data=f"Balance: ₱{new_balance}"
                )
                messages.success(request, f"Balance for {customer.full_name} has been successfully updated.")
            except:
                messages.error(request, "Invalid balance amount.")
    return redirect('view_customer', customer_id=customer.id)


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
            
            if getattr(api, '_connection_failed', False):
                data['mt_status'] = 'API Unreachable'
            else:
                # If the customer is completely disconnected, check if the ENTIRE router is offline (lost uplink)
                if data['mt_status'] == "Disconnected":
                    try:
                        ping_res = api._get_api().get_resource('/').call('ping', {'address': '8.8.8.8', 'count': '1'})
                        if ping_res and len(ping_res) > 0:
                            result = ping_res[0]
                            loss = int(result.get('packet-loss', 100))
                            if loss == 100 or result.get('status') in ['no route to host', 'timeout']:
                                data['mt_status'] = 'Offline (Router Off)'
                    except Exception:
                        pass # Ignore ping errors, just leave as Disconnected
                
        except Exception:
            data['mt_status'] = 'API Unreachable'

    # Add context to disconnected status if it wasn't caught by the ping check
    if data['mt_status'] == 'Disconnected':
        if customer.status == 'active':
            if customer.barangay and customer.barangay.health_status == 'Outage':
                data['mt_status'] = 'Area Outage (Barangay)'
            elif customer.mikrotik_device and customer.mikrotik_device.health_status == 'Outage':
                data['mt_status'] = 'Network Outage (Router)'
            elif customer.health_status == 'Outage':
                data['mt_status'] = 'Service Outage'
            else:
                data['mt_status'] = 'Disconnected (Inactive)'
        elif customer.status == 'suspended':
            data['mt_status'] = 'Suspended'
        else:
            data['mt_status'] = f'Disconnected ({customer.get_status_display()})'
            
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
        'all_customers': Customer.objects.all().order_by('full_name'),

        'grand_total': grand_total,
        'filtered_range_total': filtered_range_total,
        'total_today': total_today,
        'total_yesterday': total_yesterday,

        'chart_labels_js': json.dumps(chart_labels),
        'chart_values_js': json.dumps(chart_values),
    }
    
    q = request.GET.copy()
    if 'page' in q:
        del q['page']
    context['query_params'] = q.urlencode()

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

    # Dynamically resolve target names based on table_name
    from .models import Customer, Payment, AddOnRequest, SubscriptionPlan, Agent, SystemAdmin, Barangay, AccountType
    from network_manager.models import MikrotikDevice, NapBox

    # Initialize all targets to None
    for log in page_obj:
        log.target_customer = None
        log.target_icon = "fas fa-cube" # default icon

    # Group record IDs by table
    from collections import defaultdict
    table_ids = defaultdict(list)
    for log in page_obj:
        if str(log.record_id).isdigit(): # ensure it's a valid PK
            table_ids[log.table_name].append(log.record_id)
        
    # Bulk fetch names
    resolved_names = defaultdict(dict)
    
    if 'Customer' in table_ids:
        qs = Customer.objects.filter(id__in=table_ids['Customer']).values('id', 'full_name')
        resolved_names['Customer'] = {str(c['id']): (c['full_name'], 'fas fa-user') for c in qs}
        
    if 'Payment' in table_ids:
        qs = Payment.objects.filter(id__in=table_ids['Payment']).select_related('customer').values('id', 'customer__full_name')
        resolved_names['Payment'] = {str(p['id']): (p['customer__full_name'] or 'Unknown', 'fas fa-user-circle') for p in qs}
        
    if 'AddOnRequest' in table_ids:
        qs = AddOnRequest.objects.filter(id__in=table_ids['AddOnRequest']).select_related('customer').values('id', 'customer__full_name')
        resolved_names['AddOnRequest'] = {str(a['id']): (a['customer__full_name'] or 'Unknown', 'fas fa-plus-circle') for a in qs}
        
    if 'MikrotikDevice' in table_ids:
        qs = MikrotikDevice.objects.filter(id__in=table_ids['MikrotikDevice']).values('id', 'device_name')
        resolved_names['MikrotikDevice'] = {str(m['id']): (m['device_name'], 'fas fa-server') for m in qs}
        
    if 'NapBox' in table_ids:
        qs = NapBox.objects.filter(id__in=table_ids['NapBox']).values('id', 'napbox_no')
        resolved_names['NapBox'] = {str(n['id']): (n['napbox_no'], 'fas fa-box') for n in qs}
        
    if 'SubscriptionPlan' in table_ids:
        qs = SubscriptionPlan.objects.filter(id__in=table_ids['SubscriptionPlan']).values('id', 'name')
        resolved_names['SubscriptionPlan'] = {str(s['id']): (s['name'], 'fas fa-wifi') for s in qs}
        
    if 'Agent' in table_ids:
        qs = Agent.objects.filter(id__in=table_ids['Agent']).values('id', 'name')
        resolved_names['Agent'] = {str(a['id']): (a['name'], 'fas fa-user-tie') for a in qs}
        
    if 'SystemAdmin' in table_ids:
        qs = SystemAdmin.objects.filter(id__in=table_ids['SystemAdmin']).values('id', 'username')
        resolved_names['SystemAdmin'] = {str(s['id']): (s['username'], 'fas fa-user-shield') for s in qs}
        
    if 'Barangay' in table_ids:
        qs = Barangay.objects.filter(id__in=table_ids['Barangay']).values('id', 'name')
        resolved_names['Barangay'] = {str(b['id']): (b['name'], 'fas fa-map-marker-alt') for b in qs}
        
    if 'AccountType' in table_ids:
        qs = AccountType.objects.filter(id__in=table_ids['AccountType']).values('id', 'type_name')
        resolved_names['AccountType'] = {str(a['id']): (a['type_name'], 'fas fa-tags') for a in qs}

    # Attach to logs
    for log in page_obj:
        name = None
        icon = None
        
        # Prefer the new target_name field in the model if it exists
        if hasattr(log, 'target_name') and log.target_name:
            name = log.target_name
            # Still determine the icon based on table_name
            if log.table_name == 'Customer': icon = 'fas fa-user'
            elif log.table_name == 'Payment': icon = 'fas fa-user-circle'
            elif log.table_name == 'AddOnRequest': icon = 'fas fa-plus-circle'
            elif log.table_name == 'MikrotikDevice': icon = 'fas fa-server'
            elif log.table_name == 'NapBox': icon = 'fas fa-box'
            elif log.table_name == 'SubscriptionPlan': icon = 'fas fa-wifi'
            elif log.table_name == 'Agent': icon = 'fas fa-user-tie'
            elif log.table_name == 'SystemAdmin': icon = 'fas fa-user-shield'
            elif log.table_name == 'Barangay': icon = 'fas fa-map-marker-alt'
            elif log.table_name == 'AccountType': icon = 'fas fa-tags'
            
        # Fallback to the DB lookup for older logs before the migration
        elif log.table_name in resolved_names:
            name, icon = resolved_names[log.table_name].get(str(log.record_id), (None, None))
            
        if name:
            log.target_customer = name
            log.target_icon = icon or "fas fa-cube"

    # Attach actor roles for the USER column
    admin_roles = dict(SystemAdmin.objects.values_list('username', 'role'))
    agent_names = set(Agent.objects.values_list('user__username', flat=True))
    
    for log in page_obj:
        user_str = log.changed_by or 'Unknown'
        if user_str.startswith('System/'):
            log.actor_role = 'System'
        elif user_str in admin_roles:
            log.actor_role = admin_roles[user_str]
        elif user_str in agent_names:
            log.actor_role = 'Agent'
        else:
            log.actor_role = 'User'

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
        'query_params': query_params.urlencode(),
        'page_range': page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
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
        'now': now,
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
        new_plan_id = request.POST.get('new_plan_id')
        
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

            with transaction.atomic():
                # Lock the customer row for atomic update
                locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)
                
                # --- UPGRADE PLAN LOGIC ---
                is_upgrade = False
                is_downgrade = False
                old_plan_name = locked_customer.plan.name if locked_customer.plan else "None"
                
                if new_plan_id and str(locked_customer.plan_id) != str(new_plan_id):
                    new_plan = SubscriptionPlan.objects.filter(id=new_plan_id).first()
                    if new_plan:
                        old_price = float(locked_customer.plan.price) if locked_customer.plan else 0.0
                        monthly_price = float(new_plan.price)
                        locked_customer.plan = new_plan
                        if monthly_price > old_price:
                            is_upgrade = True
                        else:
                            is_downgrade = True
                        locked_customer.save() # Triggers Mikrotik Sync
                # --------------------------
                
                # --- Option B: Wallet/Advance Payment Logic ---
                amount_for_time = 0.0
                advance_payment = 0.0
                
                if monthly_price > 0:
                    if amount_float >= monthly_price:
                        # Pay exactly 1 month, rest goes to wallet
                        amount_for_time = monthly_price
                        advance_payment = amount_float - monthly_price
                    else:
                        # Partial payment, all goes to time
                        amount_for_time = amount_float
                else:
                    amount_for_time = amount_float

                # Calculate new expiration using ONLY the amount meant for time
                new_expiry = calculate_new_expiration_date(current_exp, amount_for_time, monthly_price)

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
                payment = Payment.objects.create(
                    customer=locked_customer,
                    username=locked_customer.pppoe_username,
                    plan_name=locked_customer.plan.name if locked_customer.plan else None,
                    amount=amount, 
                    payment_method=payment_method, 
                    reference_no=reference_no, 
                    reason=reason, 
                    expires_at=new_expiry,
                    adjusted_by=request.user.username,
                    paid_at=timezone.now()
                )

                # Send Notification
                Notification.objects.create(
                    title=f"Payment Received: ₱{amount}",
                    message=f"{locked_customer.full_name} paid via {payment_method}.",
                    notification_type='payment',
                    link=f"/logs/payments/"
                )

            # 5. Mikrotik API Reactivation & Comments
            if customer.mikrotik_device:
                try:
                    from network_manager.services import MikrotikAPI
                    api = MikrotikAPI(customer.mikrotik_device)
                    
                    # Mikrotik Format: paid (date) exp (date) . plan . method . admin
                    expiry_str = new_expiry.strftime('%b %d, %Y')
                    paid_str = timezone.now().strftime('%b %d, %Y')
                    plan_name = customer.plan.name if customer.plan else "No Plan"
                    admin_name = request.user.username if request.user.is_authenticated else "Admin"
                    comment_text = f"paid {paid_str} exp {expiry_str} . {plan_name} . {payment_method} . {admin_name} . {reason}"
                    api.set_pppoe_comment(customer.pppoe_username, comment_text)
                    
                    if was_suspended:
                        # 1. Enable the user (Removes bridge drop and enables secret)
                        api.enable_pppoe_user(customer.pppoe_username)
                        # 2. Update the profile back to their plan, or default if none
                        target_profile = customer.plan.name if customer.plan and customer.plan.name else "default"
                        api.set_user_pppoe_profile(customer.pppoe_username, target_profile)
                        # 3. Kick them so they reconnect and get the new profile
                        api.kick_active_user(customer.pppoe_username)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to sync renewal for {customer.pppoe_username} on MikroTik: {e}")

            # 4. Success Output
            
            # Generate Messenger Template
            messenger_msg = f"Hi {customer.full_name},\n\nThank you for your payment of ₱{amount} via {payment_method}. Your internet connection is now active until {new_expiry.strftime('%B %d, %Y')}."
            if is_upgrade:
                messenger_msg += f"\n\nThank you for upgrading to {new_plan.name}! Enjoy your faster speeds."
            elif is_downgrade:
                messenger_msg += f"\n\nYour plan has been successfully updated to {new_plan.name}. If you wish to upgrade soon for faster speeds, you can always let us know!"
            
            context = {
                'customer': customer,
                'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S'),
                'adjusted_by': request.user.username,
                'action_type': 'Standard Renewal',
                'amount': amount,
                'next_url': next_url,
                'messenger_template': messenger_msg,
            }
            return render(request, 'billing/payment_success.html', context)

    # GET Request: Setup defaults
    current_expiry = customer.expires_at or timezone.now()
    start_default_str = current_expiry.strftime('%Y-%m-%dT%H:%M:%S')
    
    # Add roughly one month for the default end date
    end_default = current_expiry + timezone.timedelta(days=30)
    end_default_str = end_default.strftime('%Y-%m-%dT%H:%M:%S')

    plans = SubscriptionPlan.objects.all().order_by('price')

    context = {
        'customer': customer,
        'plans': plans,
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
@role_required(['Admin', 'Editor', 'CSR'])
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
    
    q = request.GET.copy()
    if 'page' in q:
        del q['page']
    context['query_params'] = q.urlencode()
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
    
    q = request.GET.copy()
    if 'page' in q:
        del q['page']
    context['query_params'] = q.urlencode()
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
    
    # Fetch all active customers for Walk-in Payment dropdown
    all_customers = Customer.objects.filter(status='active').values('pppoe_username', 'full_name')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'all_customers': all_customers,
    }
    
    q = request.GET.copy()
    if 'page' in q:
        del q['page']
    context['query_params'] = q.urlencode()
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
        
        Notification.objects.create(
            title="Cignal Play / Add-on Applied",
            message=f"{customer.full_name} applied for {plan_name}.",
            notification_type='cignal',
            link=f"/customer/{customer.id}/cignal-logs/"
        )
        
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
            from django.db.models import Q
            customer = Customer.objects.filter(
                Q(full_name__iexact=u, portal_password=p) | 
                Q(phone=u, portal_password=p)
            ).first()
            
            if customer:
                request.session['customer_id'] = customer.id
                next_url = request.POST.get('next') or request.GET.get('next')
                return redirect(next_url if next_url else 'customer_portal:portal_dashboard')
            else:
                messages.error(request, 'Invalid username or password.')

        except Customer.DoesNotExist:
            messages.error(request, 'Invalid username or password.')
            
    return render(request, 'billing/login.html')

@role_required(['Admin'])
@login_required
def edit_payment_log_view(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    
    if request.method == 'POST':
        old_method = payment.payment_method
        old_amount = payment.amount
        old_ref = payment.reference_no
        old_reason = payment.reason

        new_method = request.POST.get('payment_method')
        new_amount = request.POST.get('amount')
        new_ref = request.POST.get('reference_no', '')
        new_reason = request.POST.get('reason', '')

        # Construct audit log remarks
        changes = []
        if str(old_method) != str(new_method):
            changes.append(f"Method: {old_method} -> {new_method}")
        if str(old_amount) != str(new_amount):
            changes.append(f"Amount: {old_amount} -> {new_amount}")
        if str(old_ref) != str(new_ref):
            changes.append(f"Reference: {old_ref} -> {new_ref}")
        if str(old_reason) != str(new_reason):
            changes.append(f"Reason: {old_reason} -> {new_reason}")

        if changes:
            payment.payment_method = new_method
            if new_amount:
                payment.amount = new_amount
            payment.reference_no = new_ref
            payment.reason = new_reason
            payment.save()

            AuditLog.objects.create(
                admin_user=request.user,
                customer=payment.customer,
                action_type='Edit Payment Log',
                remarks=f"Edited Payment #{payment.id}. Changes: {', '.join(changes)}"
            )
            messages.success(request, f"Payment #{payment.id} successfully updated.")
        
        return redirect('payment_logs')

    context = {
        'payment': payment
    }
    return render(request, 'billing/edit_payment_log.html', context)



@login_required
def live_addon_requests_api(request):
    requests = AddOnRequest.objects.filter(status='Pending').select_related('customer').order_by('-requested_at')
    data = []
    for req in requests:
        data.append({
            'id': req.id,
            'customer_name': req.customer.full_name,
            'customer_id': req.customer.id,
            'addon_type': req.addon_type,
            'requested_at': req.requested_at.strftime('%b %d, %I:%M %p')
        })
    return JsonResponse({'status': 'success', 'data': data})

@login_required
@require_POST
def resolve_addon_request_api(request):
    import json
    try:
        body = json.loads(request.body)
        req_id = body.get('request_id')
        if req_id:
            addon_req = AddOnRequest.objects.get(id=req_id)
            addon_req.status = 'Resolved'
            addon_req.save()
            return JsonResponse({'status': 'success'})
    except AddOnRequest.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def notifications_list_view(request):
    notification_list = Notification.objects.all().order_by('-created_at')
    
    # Filter by type if provided
    notif_type = request.GET.get('type')
    if notif_type and notif_type != 'all':
        notification_list = notification_list.filter(notification_type=notif_type)
        
    # Filter by read status if provided
    is_read = request.GET.get('status')
    if is_read == 'unread':
        notification_list = notification_list.filter(is_read=False)
    elif is_read == 'read':
        notification_list = notification_list.filter(is_read=True)

    paginator = Paginator(notification_list, 20)  # Show 20 notifications per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'billing/notifications.html', {
        'page_obj': page_obj,
        'current_type': notif_type or 'all',
        'current_status': is_read or 'all',
    })


@login_required
def api_notifications(request):
    notifications = Notification.objects.all()[:15]
    unread_count = Notification.objects.filter(is_read=False).count()
    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
            'link': n.link or '#'
        })
    return JsonResponse({'status': 'success', 'unread_count': unread_count, 'notifications': data})

@login_required
@require_POST
def api_mark_notification_read(request, notif_id):
    try:
        notif = Notification.objects.get(id=notif_id)
        notif.is_read = True
        notif.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

@login_required
@require_POST
def api_mark_all_notifications_read(request):
    Notification.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success'})



def api_network_alerts(request):
    from .models import Barangay, Customer
    from network_manager.models import MikrotikDevice
    active_device_alerts = MikrotikDevice.objects.exclude(health_status='Excellent')
    active_barangay_alerts = Barangay.objects.exclude(health_status='Excellent')
    active_customer_alerts = Customer.objects.exclude(health_status__in=['Excellent', 'Good', 'Stable', 'Strong']).filter(status='active')
    
    data = []
    for d in active_device_alerts:
        data.append({'type': 'device', 'id': d.id, 'name': d.device_name + ' (Router)', 'status': d.health_status, 'reason': d.health_reason})
    for b in active_barangay_alerts:
        data.append({'type': 'barangay', 'id': b.id, 'name': b.name + ' (Barangay)', 'status': b.health_status, 'reason': b.health_reason})
    for c in active_customer_alerts:
        data.append({'type': 'customer', 'id': c.id, 'name': c.full_name + ' (Customer)', 'status': c.health_status, 'reason': c.health_reason})
        
    return JsonResponse({'status': 'success', 'alerts': data})


def api_active_pppoe_usernames(request):
    from network_manager.models import MikrotikDevice
    from network_manager.services import MikrotikAPI
    from django.http import JsonResponse
    
    devices = MikrotikDevice.objects.all()
    active_usernames = set()
    offline_routers = []
    
    for device in devices:
        try:
            api = MikrotikAPI(device)
            active_users = api.get_active_pppoe_users()
            for au in active_users:
                if au.get('name'):
                    active_usernames.add(au.get('name'))
        except Exception:
            offline_routers.append(device.id)
            
    return JsonResponse({
        'status': 'success', 
        'active_usernames': list(active_usernames),
        'offline_routers': offline_routers
    })

@role_required(['Admin', 'Editor'])
@login_required
def bulk_transfer_router(request):
    """
    Handles bulk moving customers to a different Mikrotik router.
    """
    if request.method == 'POST':
        customer_ids = request.POST.getlist('customer_ids')
        target_device_id = request.POST.get('target_device_id')
        
        if not customer_ids or not target_device_id:
            messages.error(request, 'Please select customers and a target router.')
            return redirect('customer_list')
            
        try:
            from network_manager.models import MikrotikDevice
            target_device = MikrotikDevice.objects.get(id=target_device_id)
            
            transferred_count = 0
            for cid in customer_ids:
                customer = Customer.objects.get(id=cid)
                if str(customer.mikrotik_device_id) != str(target_device_id):
                    # Keep track of old device ID so the signal knows to delete the secret
                    customer._original_mikrotik_device_id = customer.mikrotik_device_id
                    
                    customer.mikrotik_device = target_device
                    customer.save() # Triggers post_save signal
                    transferred_count += 1
                    
            messages.success(request, f'Successfully transferred {transferred_count} customers to {target_device.device_name}.')
        except Exception as e:
            messages.error(request, f'Error during transfer: {str(e)}')
            
    return redirect('customer_list')

@login_required
@role_required(['Admin'])
def revert_transfer_payment(request, payment_id):
    if request.method == 'POST':
        payment = get_object_or_404(Payment, id=payment_id)
        wrong_customer = payment.customer
        new_customer_id = request.POST.get('new_customer_id')
        
        if not new_customer_id:
            messages.error(request, "You must select a new customer to transfer the payment to.")
            return redirect(request.META.get('HTTP_REFERER', 'payment_logs'))
            
        new_customer = get_object_or_404(Customer, id=new_customer_id)
        
        if wrong_customer.id == new_customer.id:
            messages.error(request, "Cannot transfer payment to the same customer.")
            return redirect(request.META.get('HTTP_REFERER', 'payment_logs'))

        with transaction.atomic():
            # Lock both customers
            wrong_customer = Customer.objects.select_for_update().get(pk=wrong_customer.pk)
            new_customer = Customer.objects.select_for_update().get(pk=new_customer.pk)
            
            # --- Revert Wrong Customer ---
            monthly_price = float(wrong_customer.plan.price) if wrong_customer.plan else 0.0
            if monthly_price > 0:
                days_to_subtract = float(payment.amount) / (monthly_price / 30)
                from datetime import timedelta
                if wrong_customer.expires_at:
                    wrong_customer.expires_at = wrong_customer.expires_at - timedelta(days=days_to_subtract)
            
            wrong_customer.outstanding_balance += payment.amount
            wrong_customer.save()
            
            # --- Apply to New Customer ---
            monthly_price_new = float(new_customer.plan.price) if new_customer.plan else 0.0
            current_exp = new_customer.expires_at if (new_customer.expires_at and new_customer.expires_at > timezone.now()) else timezone.now()
            new_expiry = calculate_new_expiration_date(current_exp, float(payment.amount), monthly_price_new)
            
            was_suspended = new_customer.status in ['suspended', 'inactive', 'expired']
            new_customer.expires_at = new_expiry
            new_customer.outstanding_balance -= payment.amount
            if was_suspended:
                new_customer.status = 'active'
            new_customer.save()
            
            # Transfer the payment record
            payment.customer = new_customer
            payment.username = new_customer.pppoe_username
            payment.plan_name = new_customer.plan.name if new_customer.plan else None
            payment.expires_at = new_expiry
            payment.reason = f"[TRANSFERRED FROM {wrong_customer.full_name}] " + (payment.reason or "")
            payment.save()
            
            from .models import SystemLog
            SystemLog.objects.create(
                table_name='Payment',
                record_id=str(payment.id),
                action='UPDATE',
                changed_by=request.user.username,
                target_name=new_customer.full_name,
                old_data=f"Belonged to {wrong_customer.full_name}",
                new_data=f"Transferred to {new_customer.full_name}"
            )

        # --- Mikrotik Logic (Outside Atomic to prevent DB locks during network calls) ---
        from network_manager.services import MikrotikAPI
        # Kick wrong customer so router redials and suspends if due
        if wrong_customer.mikrotik_device:
            try:
                api_wrong = MikrotikAPI(wrong_customer.mikrotik_device)
                api_wrong.kick_active_user(wrong_customer.pppoe_username)
            except Exception as e:
                pass # Non-critical
                
        # Reactivate new customer
        if new_customer.mikrotik_device:
            try:
                api_new = MikrotikAPI(new_customer.mikrotik_device)
                
                expiry_str = new_expiry.strftime('%b %d, %Y')
                paid_str = payment.created_at.strftime('%b %d, %Y')
                plan_name = new_customer.plan.name if new_customer.plan else "No Plan"
                comment_text = f"paid {paid_str} exp {expiry_str} . {plan_name} . {payment.payment_method} . Transfer"
                api_new.set_pppoe_comment(new_customer.pppoe_username, comment_text)
                
                if was_suspended and new_customer.plan and new_customer.plan.name:
                    api_new.enable_pppoe_user(new_customer.pppoe_username)
                    api_new.kick_active_user(new_customer.pppoe_username)
            except Exception as e:
                pass # Non-critical

        messages.success(request, f"Payment successfully transferred from {wrong_customer.full_name} to {new_customer.full_name}.")
        return redirect(request.META.get('HTTP_REFERER', 'payment_logs'))
    return redirect('payment_logs')


@login_required
def apply_cignal_addon(request):
    if request.method == 'POST':
        request_id = request.POST.get('request_id')
        customer_id = request.POST.get('customer_id')
        cignalplay_no = request.POST.get('cignalplay_no')
        cignalplay_date = request.POST.get('cignalplay_date')
        addon_type = request.POST.get('addon_type')
        
        customer = get_object_or_404(Customer, id=customer_id)
        
        # Resolve request
        if request_id:
            try:
                addon_req = AddOnRequest.objects.get(id=request_id)
                addon_req.status = 'Resolved'
                addon_req.save()
            except AddOnRequest.DoesNotExist:
                pass
                
        # Update customer profile
        customer.cignalplay_no = cignalplay_no
        customer.cignalplay_date = cignalplay_date
        customer.cignalplay_adjustedby = request.user.username
        customer.save()
        
        # Log to CignalPlay table
        CignalPlay.objects.create(
            customer=customer,
            plan_name=addon_type or 'Cignal Play Add-on',
            start_date=cignalplay_date,
            adjusted_by=request.user.username
        )
        
        # Notification
        Notification.objects.create(
            title="Cignal Add-on Applied",
            message=f"{customer.full_name} applied for {addon_type or 'Cignal Play'} (Acct: {cignalplay_no}).",
            notification_type='cignal',
            link=f"/customer/{customer.id}/cignal-logs/"
        )
        
        messages.success(request, f"Add-on applied successfully for {customer.full_name}.")
        
    return redirect(request.META.get('HTTP_REFERER', 'live_monitoring'))


@login_required
def online_staff_api(request):
    from django.core.cache import cache
    from django.contrib.auth.models import User
    
    # We only check users who could be staff (all User models typically in this app)
    # This might be <20 users, so iterating over them and checking cache is fast enough.
    staff_users = User.objects.all()
    
    data = []
    for u in staff_users:
        # The ActiveUserMiddleware sets this cache key for 5 minutes when a user is active
        if cache.get(f'seen_user_{u.id}'):
            role = getattr(u, 'role', 'Staff')
            data.append({
                'username': u.username,
                'role': role
            })
        
    return JsonResponse({'status': 'success', 'data': data})

@role_required(['Admin', 'Editor', 'Technician', 'Agent'])
@login_required
@require_POST
def approve_cignal_request(request, request_id):
    from billing.models import AddOnRequest
    addon_req = get_object_or_404(AddOnRequest, pk=request_id)
    cignal_no = request.POST.get('cignal_play_no')
    cignal_date = request.POST.get('cignal_date')
    if not cignal_no or not cignal_date:
        messages.error(request, 'Cignal Play No and Date are required.')
        return redirect('add_on_requests')
    customer = addon_req.customer
    customer.cignalplay_no = cignal_no
    try:
        customer.cignalplay_date = timezone.datetime.fromisoformat(cignal_date).date()
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect('add_on_requests')
    customer.save()
    addon_req.status = 'Resolved'
    addon_req.save()
    messages.success(request, f'Cignal request for {customer.full_name} approved and applied.')
    return redirect('add_on_requests')

