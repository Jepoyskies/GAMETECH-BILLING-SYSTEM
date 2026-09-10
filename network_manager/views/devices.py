from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from billing.decorators import role_required
from django.contrib import messages
from django.http import JsonResponse
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

@login_required
def device_list(request):
    from django.db.models import Count, Q
    devices = MikrotikDevice.objects.annotate(
        customer_count=Count('customer', filter=Q(customer__status='active'))
    ).order_by('device_name')
    return render(request, 'network_manager/device_list.html', {'devices': devices})

@role_required(['Admin', 'CSR'])
@login_required
def add_device(request):
    if request.method == 'POST':
        device_name = request.POST.get('device_name')
        ip_address = request.POST.get('ip_address')
        api_username = request.POST.get('api_username')
        api_password = request.POST.get('api_password')
        api_port = request.POST.get('api_port', 8728)
        api_port_8700 = request.POST.get('api_port_8700') or 8700

        MikrotikDevice.objects.create(
            device_name=device_name,
            ip_address=ip_address,
            api_username=api_username,
            api_password=api_password,
            api_port=api_port,
            api_port_8700=api_port_8700
        )
        messages.success(
            request, f"Device '{device_name}' added successfully!")
        return redirect('device_list')

    return render(request, 'network_manager/add_device.html')

@role_required(['Admin', 'CSR'])
@login_required
def edit_device(request, device_id):
    device = get_object_or_404(MikrotikDevice, id=device_id)
    if request.method == 'POST':
        device.device_name = request.POST.get('device_name')
        device.ip_address = request.POST.get('ip_address')
        device.api_username = request.POST.get('api_username')
        device.api_port = request.POST.get('api_port')
        device.api_port_8700 = request.POST.get('api_port_8700') or device.api_port_8700 or 8700

        # Only update password if they typed a new one!
        new_password = request.POST.get('api_password')
        if new_password:
            device.api_password = new_password

        device.save()
        messages.success(
            request, f"Device '{device.device_name}' updated successfully!")
        return redirect('device_list')

    return render(request, 'network_manager/edit_device.html', {'device': device})

@role_required(['Admin', 'CSR'])
@login_required
def delete_device(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        device_name = device.device_name
        device.delete()
        messages.success(
            request, f"Device '{device_name}' deleted successfully!")
    return redirect('device_list')

@login_required
def test_device_connection(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)

        try:
            from network_manager.services import MikrotikAPI
            api = MikrotikAPI(device)
            # Try to fetch something simple to confirm connection
            api_conn = api._get_api()
            system_identity = api_conn.get_resource('/system/identity')
            identity = system_identity.get()[0]['name']
            api.connection.disconnect()
            
            return JsonResponse({'status': 'success', 'message': f'Connected successfully to {device.device_name} ({identity})'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Connection failed: {e}'})

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_device_users(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)

        try:
            from network_manager.services import MikrotikAPI
            from billing.models import Customer, SubscriptionPlan
            
            api = MikrotikAPI(device)
            secrets = api.get_ppp_secrets()
            
            added = 0
            for secret in secrets:
                name = secret.get('name')
                if name and not Customer.objects.filter(pppoe_username=name).exists():
                    status = 'inactive' if secret.get('disabled') == 'true' else 'active'
                    
                    # Extract full name from comment if available
                    comment = secret.get('comment', '').strip()
                    full_name = comment if comment else name
                    
                    # Try to map profile to SubscriptionPlan
                    profile_name = secret.get('profile', '')
                    plan = SubscriptionPlan.objects.filter(name__iexact=profile_name).first()
                    
                    Customer.objects.create(
                        full_name=full_name,
                        pppoe_username=name,
                        pppoe_password=secret.get('password', ''),
                        mac_address=secret.get('caller-id', ''),
                        mikrotik_device=device,
                        plan=plan,
                        status=status,
                        created_form_by='MikroTik Sync'
                    )
                    added += 1
            
            return JsonResponse({'status': 'success', 'message': f'Synced successfully. Imported {added} new customers from {device.device_name}.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Sync failed: {e}'})

@login_required
def device_hardware_api(request, device_id):
    device = get_object_or_404(MikrotikDevice, id=device_id)
    try:
        from network_manager.services import MikrotikAPI
        api = MikrotikAPI(device)
        api_conn = api._get_api()
        
        # Get System Resources (CPU, Memory, Uptime)
        resource_data = api_conn.get_resource('/system/resource').get()[0]
        
        # Get Routerboard info for temperature/voltage (if supported)
        health_data = []
        try:
            health_data = api_conn.get_resource('/system/health').get()
        except Exception:
            pass # Not all routers support /system/health

        api.connection.disconnect()
        
        # We can also call our new wrapper method if needed, but the above is fine.
        # Let's get the optical readings via the wrapper.
        optical_data = api.get_optical_readings()
        
        return JsonResponse({
            'status': 'success',
            'cpu_load': resource_data.get('cpu-load'),
            'free_memory': resource_data.get('free-memory'),
            'total_memory': resource_data.get('total-memory'),
            'free_hdd_space': resource_data.get('free-hdd-space'),
            'total_hdd_space': resource_data.get('total-hdd-space'),
            'uptime': resource_data.get('uptime'),
            'resource': resource_data,
            'health': health_data,
            'optical': optical_data
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def setup_router_profiles(request, device_id):
    """
    Syncs all Django Subscription Plans to the Mikrotik router as PPPoE Profiles.
    """
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        from billing.models import SubscriptionPlan
        from network_manager.sync_services import MikrotikAPI as MikrotikSyncAPI
        
        try:
            api = MikrotikSyncAPI(
                ip_address=device.ip_address,
                username=device.api_username,
                password=device.api_password,
                port=device.api_port
            )
            connection, router_api = api._get_api_connection()
            profile_api = router_api.get_resource('/ppp/profile')
            
            plans = SubscriptionPlan.objects.all()
            success_count = 0
            
            import re
            for plan in plans:
                # Format rate limit string e.g., '10M/10M' (Mikrotik standard rx/tx)
                def extract_speed(speed_str):
                    match = re.search(r'\d+', str(speed_str))
                    return match.group(0) if match else "1"
                
                speed_up = extract_speed(plan.speed_up)
                speed_down = extract_speed(plan.speed_down)
                rate_limit_str = f"{speed_up}M/{speed_down}M"
                
                existing = profile_api.get(name=plan.name)
                if existing:
                    profile_id = existing[0].get('id') or existing[0].get('.id')
                    profile_api.set(
                        id=profile_id,
                        **{'rate-limit': rate_limit_str}
                    )
                else:
                    profile_api.add(
                        name=plan.name,
                        **{'rate-limit': rate_limit_str}
                    )
                success_count += 1
                
            connection.disconnect()
            messages.success(request, f'Successfully synced {success_count} Subscription Plans to {device.device_name}!')
        except Exception as e:
            messages.error(request, f'Failed to setup router: {str(e)}')
            
    return redirect('device_list')

