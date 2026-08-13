from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import MikrotikDevice
from .services import MikrotikAPI



@login_required
def device_list(request):
    devices = MikrotikDevice.objects.all().order_by('device_name')
    return render(request, 'network_manager/device_list.html', {'devices': devices})


@login_required
def add_device(request):
    if request.method == 'POST':
        device_name = request.POST.get('device_name')
        ip_address = request.POST.get('ip_address')
        api_username = request.POST.get('api_username')
        api_password = request.POST.get('api_password')
        api_port = request.POST.get('api_port', 8728)
        api_port_8700 = request.POST.get('api_port_8700', 8700)

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


@login_required
def edit_device(request, device_id):
    device = get_object_or_404(MikrotikDevice, id=device_id)
    if request.method == 'POST':
        device.device_name = request.POST.get('device_name')
        device.ip_address = request.POST.get('ip_address')
        device.api_username = request.POST.get('api_username')
        device.api_port = request.POST.get('api_port')
        device.api_port_8700 = request.POST.get('api_port_8700')

        # Only update password if they typed a new one!
        new_password = request.POST.get('api_password')
        if new_password:
            device.api_password = new_password

        device.save()
        messages.success(
            request, f"Device '{device.device_name}' updated successfully!")
        return redirect('device_list')

    return render(request, 'network_manager/edit_device.html', {'device': device})


@login_required
def delete_device(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        device_name = device.device_name
        device.delete()
        messages.success(
            request, f"Device '{device_name}' deleted successfully!")
    return redirect('device_list')

# AJAX Connection Test


@login_required
def test_device_connection(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)

        try:
            from .services import MikrotikAPI
            api = MikrotikAPI(device)
            # Try to fetch something simple to confirm connection
            api_conn = api._get_api()
            system_identity = api_conn.get_resource('/system/identity')
            identity = system_identity.get()[0]['name']
            api.connection.disconnect()
            
            return JsonResponse({'status': 'success', 'message': f'Connected successfully to {device.device_name} ({identity})'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Connection failed: {e}'})

@login_required
def sync_device_users(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)

        try:
            from .services import MikrotikAPI
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
        from .services import MikrotikAPI
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
        
        return JsonResponse({
            'status': 'success',
            'resource': resource_data,
            'health': health_data
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})





@login_required
def nap_list_view(request):
    from .models import NapBox
    naps = NapBox.objects.all().order_by('-created_at')
    return render(request, 'network_manager/nap_list.html', {'naps': naps})


@login_required
def add_nap_view(request):
    from .models import NapBox
    if request.method == 'POST':
        napbox_no = request.POST.get('napbox_no')
        nap_latitude = request.POST.get('nap_latitude')
        nap_longitude = request.POST.get('nap_longitude')
        marker_color = request.POST.get('marker_color', 'red')
        NapBox.objects.create(
            napbox_no=napbox_no,
            latitude=nap_latitude if nap_latitude else None,
            longitude=nap_longitude if nap_longitude else None,
            marker_color=marker_color
        )
        messages.success(request, 'NAP Box mapping saved successfully.')
        return redirect('nap_list')
    return render(request, 'network_manager/nap_form.html')


@login_required
def edit_nap_view(request, nap_id):
    from .models import NapBox
    nap = get_object_or_404(NapBox, id=nap_id)
    if request.method == 'POST':
        nap.napbox_no = request.POST.get('napbox_no')
        nap_latitude = request.POST.get('nap_latitude')
        nap_longitude = request.POST.get('nap_longitude')
        if nap_latitude:
            nap.latitude = nap_latitude
        if nap_longitude:
            nap.longitude = nap_longitude
        nap.marker_color = request.POST.get('marker_color', 'red')
        nap.save()
        messages.success(request, 'NAP Box mapping updated successfully.')
        return redirect('nap_list')
    return render(request, 'network_manager/nap_form.html', {'nap': nap})


@login_required
def delete_nap_view(request, nap_id):
    from .models import NapBox
    if request.method == 'POST':
        nap = get_object_or_404(NapBox, id=nap_id)
        nap.delete()
        messages.success(request, 'NAP Box deleted successfully.')
    return redirect('nap_list')

@login_required
def fbt_plc_calculator_view(request):
    """
    Renders the standalone Fiber Network (FBT/PLC) Calculator tool.
    No database context required.
    """
    return render(request, 'network_manager/fbt_plc_calculator.html')