from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from billing.decorators import role_required
from django.contrib import messages
from django.http import JsonResponse
from .models import MikrotikDevice
from .services import MikrotikAPI

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_manager(request, device_id):
    from billing.models import Customer
    from .sync_services import MikrotikAPI as MikrotikSyncAPI
    
    device = get_object_or_404(MikrotikDevice, id=device_id)
    
    # 1. Fetch Django Customers for this device OR unassigned customers
    from django.db.models import Q
    django_customers = Customer.objects.filter(
        Q(mikrotik_device=device) | Q(mikrotik_device__isnull=True)
    ).exclude(pppoe_username__isnull=True).exclude(pppoe_username='')
    django_usernames = set(django_customers.values_list('pppoe_username', flat=True))
    
    # 2. Fetch Router Users using the Sync API
    api = MikrotikSyncAPI(
        ip_address=device.ip_address,
        username=device.api_username,
        password=device.api_password,
        port=device.api_port
    )
    
    result = api.get_all_pppoe_users()
    
    clean_orphans = []
    suspicious_users = []
    missing_on_router = []
    synced = []
    
    if result.get('success'):
        router_users = result.get('data', [])
        router_usernames = set(u.get('name') for u in router_users if u.get('name'))
        
        # Categorize
        # Create a fast lookup dict for django customers by pppoe_username
        django_customer_map = {dc.pppoe_username: dc for dc in django_customers}
        
        for ru in router_users:
            name = ru.get('name')
            if not name:
                continue
            
            is_in_system = name in django_usernames
            if is_in_system:
                ru['customer'] = django_customer_map.get(name)
                ru['is_in_system'] = True
            else:
                ru['is_in_system'] = False

            if is_in_system:
                synced.append(ru)
            elif ru.get('is_suspicious'):
                suspicious_users.append(ru)
            else:
                clean_orphans.append(ru)
                
        for dc in django_customers:
            if dc.pppoe_username not in router_usernames:
                missing_on_router.append(dc)
    else:
        messages.error(request, f"Failed to connect to router: {result.get('error')}")
        
    from billing.models import Barangay
    
    all_routers = MikrotikDevice.objects.all()
    barangays = Barangay.objects.all().order_by('name')

    context = {
        'device': device,
        'clean_orphans': clean_orphans,
        'suspicious_users': suspicious_users,
        'missing_on_router': missing_on_router,
        'synced': synced,
        'all_routers': all_routers,
        'barangays': barangays,
        'api_success': result.get('success', False)
    }
    
    return render(request, 'network_manager/sync_manager.html', context)

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_push_user(request, device_id):
    if request.method == 'POST':
        pppoe_username = request.POST.get('pppoe_username')
        device = get_object_or_404(MikrotikDevice, id=device_id)
        
        from billing.models import Customer
        from .sync_services import MikrotikAPI as MikrotikSyncAPI
        
        customer = get_object_or_404(Customer, pppoe_username=pppoe_username, mikrotik_device=device)
        
        api = MikrotikSyncAPI(
            ip_address=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=device.api_port
        )
        
        profile = customer.plan.name if customer.plan else "default"
        comment_parts = [customer.full_name]
        if customer.barangay:
            comment_parts.append(customer.barangay.name)
        elif customer.address:
            comment_parts.append(customer.address[:30] + ('...' if len(customer.address) > 30 else ''))
        comment = " | ".join(comment_parts)
        
        result = api.add_pppoe_user(
            name=customer.pppoe_username,
            password=customer.pppoe_password,
            profile=profile,
            comment=comment
        )
        
        if result.get('success'):
            if customer.mikrotik_device != device:
                customer.mikrotik_device = device
                customer.save(update_fields=['mikrotik_device'])
            messages.success(request, result.get('message'))
        else:
            messages.error(request, f"Failed to push user: {result.get('error')}")
            
    return redirect('sync_manager', device_id=device_id)

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_autofix_user(request, device_id):
    """Auto-fixes a synced customer's router profile and comment to match the system database."""
    if request.method == 'POST':
        pppoe_username = request.POST.get('pppoe_username')
        device = get_object_or_404(MikrotikDevice, id=device_id)
        
        from billing.models import Customer
        from .sync_services import MikrotikAPI as MikrotikSyncAPI
        
        customer = get_object_or_404(Customer, pppoe_username=pppoe_username)
        
        api = MikrotikSyncAPI(
            ip_address=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=device.api_port
        )
        
        profile = customer.plan.name if customer.plan else "default"
        comment_parts = [customer.full_name]
        if customer.barangay:
            comment_parts.append(customer.barangay.name)
        elif customer.address:
            comment_parts.append(customer.address[:30] + ('...' if len(customer.address) > 30 else ''))
        comment = " | ".join(comment_parts)
        
        result = api.add_pppoe_user(
            name=customer.pppoe_username,
            password=customer.pppoe_password,
            profile=profile,
            comment=comment
        )
        
        if result.get('success'):
            messages.success(request, f"Successfully Auto-Fixed '{pppoe_username}' on the router!")
        else:
            messages.error(request, f"Failed to Auto-Fix '{pppoe_username}': {result.get('error')}")
            
    return redirect('sync_manager', device_id=device_id)

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_delete_user(request, device_id):
    if request.method == 'POST':
        pppoe_username = request.POST.get('pppoe_username')
        device = get_object_or_404(MikrotikDevice, id=device_id)
        
        from .sync_services import MikrotikAPI as MikrotikSyncAPI
        
        api = MikrotikSyncAPI(
            ip_address=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=device.api_port
        )
        
        result = api.delete_pppoe_user(name=pppoe_username)
        
        if result.get('success'):
            messages.success(request, result.get('message'))
        else:
            messages.error(request, f"Failed to delete user: {result.get('error')}")
            
    return redirect('sync_manager', device_id=device_id)

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_bulk_action(request, device_id):
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        usernames = request.POST.getlist('selected_users')
        device = get_object_or_404(MikrotikDevice, id=device_id)
        
        if not usernames:
            messages.warning(request, "No users selected for bulk action.")
            return redirect('sync_manager', device_id=device_id)

        from billing.models import Customer
        from .sync_services import MikrotikAPI as MikrotikSyncAPI
        
        api = MikrotikSyncAPI(
            ip_address=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=device.api_port
        )

        success_count = 0
        error_count = 0

        if action == 'bulk_delete':
            for uname in usernames:
                res = api.delete_pppoe_user(name=uname)
                if res.get('success'):
                    success_count += 1
                else:
                    error_count += 1
            messages.success(request, f"Bulk Delete: {success_count} deleted, {error_count} failed.")

        elif action == 'bulk_push':
            for uname in usernames:
                customer = Customer.objects.filter(pppoe_username=uname).first()
                if customer:
                    profile = customer.plan.name if customer.plan else "default"
                    res = api.add_pppoe_user(
                        name=customer.pppoe_username,
                        password=customer.pppoe_password,
                        profile=profile,
                        comment=customer.full_name
                    )
                    if res.get('success'):
                        if customer.mikrotik_device != device:
                            customer.mikrotik_device = device
                            customer.save(update_fields=['mikrotik_device'])
                        success_count += 1
                    else:
                        error_count += 1
            messages.success(request, f"Bulk Push: {success_count} pushed, {error_count} failed.")

        elif action == 'bulk_import':
            # Note: The import action redirects to the add_customer page or creates them automatically?
            # Creating them automatically requires default values (password, plan). 
            # We'll just create them as inactive with a default plan if possible, or redirect to a mass import form.
            # But "import to Django" usually needs manual fields. If they want Bulk Import, we'll auto-create them.
            # Let's fetch secrets to get passwords:
            all_users_res = api.get_all_pppoe_users()
            router_users_dict = {u['name']: u for u in all_users_res.get('data', [])} if all_users_res.get('success') else {}
            
            for uname in usernames:
                ru = router_users_dict.get(uname, {})
                if not Customer.objects.filter(pppoe_username=uname).exists():
                    Customer.objects.create(
                        full_name=ru.get('comment') or uname,
                        pppoe_username=uname,
                        pppoe_password=ru.get('password', ''),
                        mikrotik_device=device,
                        status='inactive',
                        created_form_by='Bulk Import'
                    )
                    success_count += 1
                else:
                    error_count += 1
            messages.success(request, f"Bulk Import: {success_count} imported, {error_count} skipped/failed.")

        else:
            messages.error(request, "Invalid bulk action.")

    return redirect('sync_manager', device_id=device_id)

