from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.views.decorators.http import require_POST
from ..decorators import role_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, Max
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime
from ..models import (
    SystemAdmin, SubscriptionPlan, Agent, AccountType,
    Customer, Barangay, Payment, Rebate, SystemLog, SmsLog, CignalPlay, AuditLog, AddOnRequest, Notification, ImprovementRequest
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar

@login_required
def api_live_monitoring_data(request):
    from django.core.cache import cache
    try:
        response_data = cache.get('live_monitoring_data')
    except Exception:
        response_data = None
    
    # Fallback if cache is empty or expired (or Redis is not running)
    if not response_data:
        from billing.utils import get_live_monitoring_data_sync
        response_data = get_live_monitoring_data_sync()
        
    return JsonResponse(response_data)

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
    one_week_ago = now - timedelta(days=7)

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
            | Q(expires_at__lte=now, expires_at__gt=one_week_ago)
        )
    elif status_filter == 'inactive':
        customers = customers.filter(expires_at__lte=one_week_ago)

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
        elif c.expires_at <= one_week_ago:
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
        'one_week_ago': one_week_ago,
    }
    
    q = request.GET.copy()
    if 'page' in q:
        del q['page']
    context['query_params'] = q.urlencode()

    return render(request, 'billing/partials/subscription_plans_table.html', context)

@login_required
def api_top_clients(request):
    filter_type = request.GET.get('filter', 'month')
    now = timezone.localtime()
    
    payments = Payment.objects.all()
    
    if filter_type == 'week':
        # Start of current week (Monday)
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        payments = payments.filter(created_at__gte=start_date)
    elif filter_type == 'year':
        payments = payments.filter(created_at__year=now.year)
    else: # 'month' is default
        payments = payments.filter(created_at__month=now.month, created_at__year=now.year)
        
    top_clients_qs = payments.values(
        'customer__full_name', 
        'customer__pppoe_username',
        'customer__plan__name'
    ).annotate(
        total_paid=Sum('amount'), 
        last_payment=Max('created_at')
    ).order_by('-total_paid')[:50] # Top 50 clients
    
    data = []
    for c in top_clients_qs:
        if c['customer__full_name'] or c['customer__pppoe_username']:
            data.append({
                'username': c['customer__pppoe_username'] or c['customer__full_name'],
                'plan_name': c['customer__plan__name'] or 'N/A',
                'total_paid': float(c['total_paid'] or 0),
            })
            
    return JsonResponse({'status': 'success', 'data': data})

@login_required
def api_popular_plans(request):
    filter_type = request.GET.get('filter', 'month')
    now = timezone.localtime()
    
    customers = Customer.objects.all()
    
    if filter_type == 'week':
        # Start of current week (Monday)
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        customers = customers.filter(created_at__gte=start_date)
    elif filter_type == 'year':
        customers = customers.filter(created_at__year=now.year)
    else: # 'month' is default
        customers = customers.filter(created_at__month=now.month, created_at__year=now.year)
        
    top_plans_qs = customers.values('plan__name').annotate(cnt=Count('id')).order_by('-cnt')[:50]
    
    data = []
    for p in top_plans_qs:
        data.append({
            'plan_name': p['plan__name'] or 'None',
            'cnt': p['cnt']
        })
        
    return JsonResponse({'status': 'success', 'data': data})

