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
def mikrotik_active_users_view(request):
    from network_manager.models import MikrotikDevice
    from ..models import Barangay
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
                    from ..models import Customer
                    affected_customers = Customer.objects.filter(mikrotik_device_id=device.id, status='active').exclude(phone__isnull=True).exclude(phone__exact='')
                    for customer in affected_customers:
                        send_semaphore_sms(customer.phone, message)
                        
        elif scope == 'barangay':
            barangay_ids = request.POST.getlist('barangay_id')
            if barangay_ids:
                from ..models import Barangay
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
                    from ..models import Customer
                    affected_customers = Customer.objects.filter(barangay_id__in=barangay_ids, status='active').exclude(phone__isnull=True).exclude(phone__exact='')
                    for customer in affected_customers:
                        send_semaphore_sms(customer.phone, message)
                        
        elif scope == 'customer':
            customer_id = request.POST.get('customer_id')
            if customer_id:
                from ..models import Customer
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
        from ..models import Barangay
        barangay = get_object_or_404(Barangay, id=item_id)
        barangay.health_status = 'Excellent'
        barangay.health_reason = ''
        barangay.save()
        messages.success(request, f"Resolved network health for barangay {barangay.name}.")
    elif scope == 'customer':
        from ..models import Customer
        customer = get_object_or_404(Customer, id=item_id)
        customer.health_status = 'Excellent'
        customer.health_reason = ''
        customer.save()
        messages.success(request, f"Resolved network health for customer {customer.full_name}.")
    elif scope == 'addon':
        from ..models import AddOnRequest
        addon = get_object_or_404(AddOnRequest, id=item_id)
        addon.status = 'Resolved'
        addon.save()
        messages.success(request, f"Resolved add-on request ({addon.addon_type}) for {addon.customer.full_name}.")
    return redirect(request.META.get('HTTP_REFERER', 'live_monitoring'))


@login_required
def live_monitoring_view(request):
    from ..models import Barangay, Customer, AddOnRequest
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
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
            
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@login_required
def downdetector_view(request):
    """
    Renders the downdetector dashboard displaying the status of monitored services.
    """
    from billing.models import MonitoredService
    services = MonitoredService.objects.all().order_by('name')
    context = {
        'page_title': 'Downdetector',
        'services': services,
    }
    return render(request, 'billing/downdetector.html', context)
