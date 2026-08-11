from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import MikrotikDevice
from .services import MikrotikAPI

@login_required
def device_list_view(request):
    devices = MikrotikDevice.objects.all().order_by('device_name')
    return render(request, 'network_manager/mikrotik_devices.html', {'devices': devices})

@login_required
def add_device_view(request):
    if request.method == 'POST':
        name = request.POST.get('device_name')
        ip = request.POST.get('ip_address')
        username = request.POST.get('api_username')
        password = request.POST.get('api_password')
        port = request.POST.get('api_port', '8728')
        
        MikrotikDevice.objects.create(
            device_name=name,
            ip_address=ip,
            api_username=username,
            api_password=password,
            api_port=port
        )
        messages.success(request, f"Device {name} added successfully!")
    return redirect('device_list')

@login_required
def edit_device_view(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        device.device_name = request.POST.get('device_name')
        device.ip_address = request.POST.get('ip_address')
        device.api_username = request.POST.get('api_username')
        # Only update password if a new one is provided
        new_password = request.POST.get('api_password')
        if new_password:
            device.api_password = new_password
        device.api_port = request.POST.get('api_port', '8728')
        device.save()
        messages.success(request, f"Device {device.device_name} updated successfully!")
    return redirect('device_list')

@login_required
def delete_device_view(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        name = device.device_name
        device.delete()
        messages.success(request, f"Device {name} deleted successfully!")
    return redirect('device_list')

@login_required
def test_connection_view(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        try:
            api = MikrotikAPI(device)
            # Just fetching active users as a connection test
            api._get_api().get_resource('/system/resource').get()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    return JsonResponse({'status': 'error', 'error': 'Invalid request'})
