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
    from ..models import Barangay, Customer
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


