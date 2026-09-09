from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from billing.decorators import role_required
from django.contrib import messages
from django.http import JsonResponse
from .models import MikrotikDevice
from .services import MikrotikAPI

@role_required(['Admin', 'Technician', 'CSR'])
@login_required
def winbox_routers(request):
    devices = MikrotikDevice.objects.all().order_by('device_name')
    return render(request, 'network_manager/winbox_routers.html', {'devices': devices})

@role_required(['Admin', 'Technician', 'CSR'])
@login_required
def winbox_dashboard(request, device_id):
    device = get_object_or_404(MikrotikDevice, id=device_id)
    
    # Check if password protection is needed
    needs_auth = request.user.role != 'Admin' and not request.user.is_superuser
    session_key = f'winbox_unlocked_{device_id}'
    
    if needs_auth and not request.session.get(session_key):
        if request.method == 'POST':
            password = request.POST.get('admin_password')
            # Hardcoded admin password for now, can be moved to settings later
            if password == 'admin123':
                request.session[session_key] = True
                messages.success(request, 'Winbox Dashboard unlocked successfully.')
                return redirect('winbox_dashboard', device_id=device.id)
            else:
                messages.error(request, 'Incorrect Admin Password.')
        return render(request, 'network_manager/winbox_auth.html', {'device': device})
        
    api = MikrotikAPI(device)
    
    secrets = api.get_ppp_secrets()
    for s in secrets:
        s['id'] = s.get('id') or s.get('.id', '')
        s['local_address'] = s.get('local-address', '')
        s['remote_address'] = s.get('remote-address', '')
        s['last_logged_out'] = s.get('last-logged-out', '')
        
    profiles = api.get_ppp_profiles()
    for p in profiles:
        p['id'] = p.get('id') or p.get('.id', '')
        p['rate_limit'] = p.get('rate-limit', '')
        p['only_one'] = p.get('only-one', '')
        p['local_address'] = p.get('local-address', '')
        p['remote_address'] = p.get('remote-address', '')
        
    active_users = api.get_active_pppoe_users()
    for a in active_users:
        a['id'] = a.get('id') or a.get('.id', '')
    
    context = {
        'device': device,
        'secrets': secrets,
        'profiles': profiles,
        'active_users': active_users,
        'active_tab': request.GET.get('tab', 'secrets')
    }
    return render(request, 'network_manager/winbox_dashboard.html', context)

@role_required(['Admin', 'Technician', 'CSR'])
@login_required
def winbox_secret_action(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        api = MikrotikAPI(device)
        action = request.POST.get('action')
        
        if action == 'add':
            success, msg = api.add_pppoe_user(
                name=request.POST.get('name'),
                password=request.POST.get('password'),
                profile=request.POST.get('profile'),
                service=request.POST.get('service', 'pppoe'),
                comment=request.POST.get('comment', ''),
                disabled='yes' if request.POST.get('disabled') == 'on' else 'no'
            )
            if success:
                messages.success(request, f"Secret added: {msg}")
            else:
                messages.error(request, f"Error adding secret: {msg}")
                
        elif action == 'edit':
            internal_id = request.POST.get('id')
            success, msg = api.update_ppp_secret(
                internal_id,
                name=request.POST.get('name'),
                password=request.POST.get('password'),
                profile=request.POST.get('profile'),
                service=request.POST.get('service', 'pppoe'),
                comment=request.POST.get('comment', ''),
                disabled='true' if request.POST.get('disabled') == 'on' else 'false'
            )
            if success:
                messages.success(request, f"Secret updated: {msg}")
            else:
                messages.error(request, f"Error updating secret: {msg}")
                
        elif action == 'delete':
            internal_id = request.POST.get('id')
            success, msg = api.delete_ppp_secret(internal_id)
            if success:
                messages.success(request, f"Secret deleted: {msg}")
            else:
                messages.error(request, f"Error deleting secret: {msg}")
                
    return redirect(f"/devices/winbox/{device_id}/?tab=secrets")

@role_required(['Admin', 'Technician', 'CSR'])
@login_required
def winbox_profile_action(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        api = MikrotikAPI(device)
        action = request.POST.get('action')
        
        # Build kwargs from form, ignoring empty ones except name
        kwargs = {
            'name': request.POST.get('name'),
            'local-address': request.POST.get('local_address', ''),
            'remote-address': request.POST.get('remote_address', ''),
            'rate-limit': request.POST.get('rate_limit', '')
        }
        # Remove empty string kwargs so RouterOS defaults take over
        kwargs = {k: v for k, v in kwargs.items() if v}
        
        if action == 'add':
            success, msg = api.add_ppp_profile(**kwargs)
            if success:
                messages.success(request, f"Profile added: {msg}")
            else:
                messages.error(request, f"Error adding profile: {msg}")
                
        elif action == 'edit':
            internal_id = request.POST.get('id')
            success, msg = api.update_ppp_profile(internal_id, **kwargs)
            if success:
                messages.success(request, f"Profile updated: {msg}")
            else:
                messages.error(request, f"Error updating profile: {msg}")
                
        elif action == 'delete':
            internal_id = request.POST.get('id')
            success, msg = api.delete_ppp_profile(internal_id)
            if success:
                messages.success(request, f"Profile deleted: {msg}")
            else:
                messages.error(request, f"Error deleting profile: {msg}")
                
    return redirect(f"/devices/winbox/{device_id}/?tab=profiles")

@role_required(['Admin', 'Technician', 'CSR'])
@login_required
def winbox_kick_action(request, device_id):
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        api = MikrotikAPI(device)
        username = request.POST.get('username')
        success, msg = api.kick_active_user(username)
        if success:
            messages.success(request, f"Kicked user {username}: {msg}")
        else:
            messages.error(request, f"Error kicking user: {msg}")
            
    return redirect(f"/devices/winbox/{device_id}/?tab=active")

