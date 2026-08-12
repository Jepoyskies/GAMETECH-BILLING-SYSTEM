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
from django.core.paginator import Paginator
from django.db.models import Q

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


# ─────────────────────────────────────────────────
#  Subscription / Service Plans
# ─────────────────────────────────────────────────

@login_required
def service_plans_view(request):
    """List all service plans."""
    plans = ServicePlan.objects.all().order_by('plan_name')
    total_plans = plans.count()
    avg_price = plans.aggregate(avg=Sum('price'))['avg']
    if total_plans > 0 and avg_price is not None:
        avg_price = round(float(avg_price) / total_plans, 2)
    else:
        avg_price = 0.00

    # Most subscribed plan
    top_plan_qs = Customer.objects.values('service_plan__plan_name').annotate(cnt=Count('id')).order_by('-cnt').first()
    top_plan_name = top_plan_qs['service_plan__plan_name'] if top_plan_qs else 'N/A'

    success_msg = request.GET.get('success')
    return render(request, 'billing/service_plans.html', {
        'plans': plans,
        'total_plans': total_plans,
        'avg_price': avg_price,
        'top_plan_name': top_plan_name,
        'success_msg': success_msg,
    })


@login_required
def add_plan_view(request):
    """Add a new service plan."""
    error = None
    data = {}
    if request.method == 'POST':
        plan_name    = request.POST.get('plan_name', '').strip()
        speed_up     = request.POST.get('speed_up', '').strip()
        speed_down   = request.POST.get('speed_down', '').strip()
        price        = request.POST.get('price', '').strip()
        validity_days = request.POST.get('validity_days', '').strip()
        description  = request.POST.get('description', '').strip()

        if not all([plan_name, speed_up, speed_down, price, validity_days]):
            error = 'Please fill in all required fields.'
            data = request.POST
        else:
            try:
                ServicePlan.objects.create(
                    plan_name=plan_name,
                    plan_code=plan_name.lower().replace(' ', '_'),
                    speed_up=int(speed_up),
                    speed_down=int(speed_down),
                    price=float(price),
                    price_monthly=float(price),
                    validity_days=int(validity_days),
                    description=description,
                )
                return redirect('/plans/?success=added')
            except Exception as e:
                error = f'Failed to add plan: {e}'
                data = request.POST

    return render(request, 'billing/add_plan.html', {'error': error, 'data': data})


@login_required
def edit_plan_view(request, plan_id):
    """Edit an existing service plan."""
    try:
        plan = ServicePlan.objects.get(pk=plan_id)
    except ServicePlan.DoesNotExist:
        return redirect('/plans/')

    error = None
    if request.method == 'POST':
        plan_name    = request.POST.get('plan_name', '').strip()
        speed_up     = request.POST.get('speed_up', '').strip()
        speed_down   = request.POST.get('speed_down', '').strip()
        price        = request.POST.get('price', '').strip()
        validity_days = request.POST.get('validity_days', '').strip()
        description  = request.POST.get('description', '').strip()

        if not all([plan_name, speed_up, speed_down, price, validity_days]):
            error = 'Please fill in all required fields.'
        else:
            try:
                plan.plan_name     = plan_name
                plan.plan_code     = plan_name.lower().replace(' ', '_')
                plan.speed_up      = int(speed_up)
                plan.speed_down    = int(speed_down)
                plan.price         = float(price)
                plan.price_monthly = float(price)
                plan.validity_days = int(validity_days)
                plan.description   = description
                plan.save()
                return redirect('/plans/?success=updated')
            except Exception as e:
                error = f'Failed to update plan: {e}'

    return render(request, 'billing/edit_plan.html', {'plan': plan, 'error': error})


@login_required
def delete_plan_view(request, plan_id):
    """AJAX endpoint to delete a plan."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)
    try:
        plan = ServicePlan.objects.get(pk=plan_id)
        plan.delete()
        return JsonResponse({'success': True})
    except ServicePlan.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Plan not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ─────────────────────────────────────────────────
#  Customer Subscriptions
# ─────────────────────────────────────────────────

@login_required
def subscription_plans_view(request):
    """Customer Subscriptions Dashboard."""
    # 1. Base Query
    customers = Customer.objects.select_related('service_plan', 'mikrotik_device').filter(
        username__isnull=False,
    ).exclude(username='').exclude(status='pull out')

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
        'username': 'username',
        'full_name': 'full_name',
        'address': 'address',
        'expires_at': 'expires_at',
        'plan_name': 'service_plan__plan_name',
        'price': 'service_plan__price',
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
            Q(username__icontains=search) | 
            Q(full_name__icontains=search) | 
            Q(address__icontains=search)
        )

    if status_filter == 'active':
        customers = customers.filter(expires_at__gt=soon)
    elif status_filter == 'expiring':
        customers = customers.filter(expires_at__gt=now, expires_at__lte=soon)
    elif status_filter == 'expired':
        customers = customers.filter(
            Q(expires_at__isnull=True) | 
            Q(expires_at__lte=now, expires_at__gt=one_month_ago)
        )
    elif status_filter == 'inactive':
        customers = customers.filter(expires_at__lte=one_month_ago)

    if device_filter:
        customers = customers.filter(mikrotik_device__device_name=device_filter)

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
                    connected_usernames[name] = {'uptime': au.get('uptime', '')}
                    
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
        customer_list = [c for c in customer_list if c.username in connected_usernames]
    elif connection_filter == 'Not Connected':
        customer_list = [c for c in customer_list if c.username not in connected_usernames]

    # Calculate Summaries (based on filtered list)
    count_active = 0
    count_expiring = 0
    count_expired = 0
    count_inactive = 0
    count_connected = 0
    count_not_connected = 0
    
    for c in customer_list:
        # Connection
        if c.username in connected_usernames:
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
        c.mt_connected = c.username in connected_usernames
        c.mt_uptime = connected_usernames.get(c.username, {}).get('uptime', '')
        c_secret = ppp_users_status.get(c.username, {})
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

