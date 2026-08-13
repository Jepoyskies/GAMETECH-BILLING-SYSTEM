from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime

from .models import (
    SystemAdmin, SubscriptionPlan, Agent, AccountType,
    Customer, Barangay, Payment
)
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI


@login_required
def dashboard_view(request):
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
            # e is caught and used in the f-string
            messages.warning(
                request, f"Could not connect to {device.device_name}: {e}")

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
            except Exception:
                # If a device is unreachable, we can skip it or log it
                pass

        # Cache for 2 seconds to prevent spamming routers
        cache.set(cache_key, data, 2)

    return JsonResponse(data, safe=False)


# ─────────────────────────────────────────────────
#  Subscription / Service Plans
# ─────────────────────────────────────────────────



# ─────────────────────────────────────────────────
#  Customer Subscriptions
# ─────────────────────────────────────────────────

@login_required
def subscription_plans_view(request):
    """Customer Subscriptions Dashboard."""
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

    return render(request, 'billing/subscription_plans.html', context)


# Replaces agents.php

def agent_list(request):
    agents = Agent.objects.all().order_by('name')
    return render(request, 'billing/agents.html', {'agents': agents})

# Replaces add_agent.php


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
    plans = SubscriptionPlan.objects.all().order_by('price')
    return render(request, 'billing/service_plans.html', {'plans': plans})


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


def delete_plan(request, plan_id):
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    plan.delete()
    messages.success(request, "Service plan deleted successfully!")
    return redirect('plan_list')


def staff_list(request):
    # Fetch all admins, ordered by the newest created
    staff_members = SystemAdmin.objects.all().order_by('-created_at')
    return render(request, 'billing/staff_and_admins.html', {'staff_members': staff_members})


def add_staff(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        role = request.POST.get('role')
        status = request.POST.get('status')
        raw_password = request.POST.get('password')

        # Check if username or email already exists to prevent errors
        if SystemAdmin.objects.filter(username=username).exists():
            messages.error(request, "That username is already taken.")
            return redirect('add_staff')

        if SystemAdmin.objects.filter(email=email).exists():
            messages.error(request, "That email is already registered.")
            return redirect('add_staff')

        # Securely hash the password
        hashed_password = make_password(raw_password)

        # Create the new staff user
        SystemAdmin.objects.create(
            username=username,
            full_name=full_name,
            email=email,
            role=role,
            status=status,
            password_hash=hashed_password
        )

        messages.success(
            request, f"Staff member '{full_name}' added successfully!")
        return redirect('staff_list')

    return render(request, 'billing/add_staff.html')


@login_required
def customer_list(request):
    customers = Customer.objects.select_related(
        'plan', 'agent', 'barangay', 'mikrotik_device').all()
    return render(request, 'billing/customer_list.html', {'customers': customers})


@login_required
def add_customer(request):
    if request.method == 'POST':
        Customer.objects.create(
            full_name=request.POST.get('full_name'),
            email=request.POST.get('email'),
            phone=request.POST.get('phone'),
            address=request.POST.get('address'),
            pppoe_username=request.POST.get('pppoe_username') or None,
            pppoe_password=request.POST.get('pppoe_password'),
            status=request.POST.get('status', 'active'),
            plan_id=request.POST.get('plan_id'),
            mikrotik_device_id=request.POST.get('device_id'),
            agent_id=request.POST.get('agent_id'),
            barangay_id=request.POST.get('barangay_id'),
            account_type_id=request.POST.get('account_type_id'),
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
        'accountTypes': AccountType.objects.all()
    }
    return render(request, 'billing/add_customer.html', context)


@login_required
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        customer.full_name = request.POST.get('full_name')
        customer.email = request.POST.get('email')
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
    mt_status = "Disconnected"
    uptime = "N/A"
    if customer.mikrotik_device and customer.pppoe_username:
        try:
            from network_manager.services import MikrotikAPI
            api = MikrotikAPI(customer.mikrotik_device)
            active_users = api.get_active_pppoe_users()
            for au in active_users:
                if au.get('name') == customer.pppoe_username:
                    mt_status = "Connected"
                    uptime = au.get('uptime', 'N/A')
                    break
        except Exception:
            pass
            
    context = {
        'customer': customer,
        'payments': payments,
        'mt_status': mt_status,
        'uptime': uptime,
    }
    return render(request, 'billing/view_customer.html', context)


@login_required
def delete_customer(request, customer_id):
    if request.method == 'POST':
        customer = get_object_or_404(Customer, id=customer_id)
        name = customer.full_name
        customer.delete()
        messages.success(request, f'Customer {name} deleted successfully!')
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
def geomap_view(request):
    return render(request, 'billing/geomap.html')

@login_required
def logs_view(request):
    return render(request, 'billing/logs.html')

@login_required
def settings_view(request):
    return render(request, 'billing/settings.html')
