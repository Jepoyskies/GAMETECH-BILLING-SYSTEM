from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from billing.decorators import role_required
from django.contrib import messages
from django.http import JsonResponse
from .models import MikrotikDevice
from .services import MikrotikAPI



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


@role_required(['Admin', 'CSR'])
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

@role_required(['Admin', 'Editor', 'CSR'])
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





@login_required
def nap_list_view(request):
    from .models import NapBox
    naps = NapBox.objects.all().order_by('-created_at')
    return render(request, 'network_manager/nap_list.html', {'naps': naps})


@role_required(['Admin', 'Editor', 'CSR'])
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


@role_required(['Admin', 'Editor', 'CSR'])
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


@role_required(['Admin', 'Editor', 'CSR'])
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
    
    orphans = []
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
            if name in django_usernames:
                # Add the Django Customer object to the router user dictionary
                ru['customer'] = django_customer_map.get(name)
                synced.append(ru)
            else:
                orphans.append(ru)
                
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
        'orphans': orphans,
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

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def setup_router_profiles(request, device_id):
    """
    Syncs all Django Subscription Plans to the Mikrotik router as PPPoE Profiles.
    """
    if request.method == 'POST':
        device = get_object_or_404(MikrotikDevice, id=device_id)
        from billing.models import SubscriptionPlan
        from .sync_services import MikrotikAPI as MikrotikSyncAPI
        
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
#   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  
 #   W I N B O X   U I   V I E W S  
 #   - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  
  
 @ r o l e _ r e q u i r e d ( [ ' A d m i n ' ,   ' T e c h n i c i a n ' ,   ' C S R ' ] )  
 @ l o g i n _ r e q u i r e d  
 d e f   w i n b o x _ r o u t e r s ( r e q u e s t ) :  
         d e v i c e s   =   M i k r o t i k D e v i c e . o b j e c t s . a l l ( ) . o r d e r _ b y ( ' d e v i c e _ n a m e ' )  
         r e t u r n   r e n d e r ( r e q u e s t ,   ' n e t w o r k _ m a n a g e r / w i n b o x _ r o u t e r s . h t m l ' ,   { ' d e v i c e s ' :   d e v i c e s } )  
  
  
 @ r o l e _ r e q u i r e d ( [ ' A d m i n ' ,   ' T e c h n i c i a n ' ,   ' C S R ' ] )  
 @ l o g i n _ r e q u i r e d  
 d e f   w i n b o x _ d a s h b o a r d ( r e q u e s t ,   d e v i c e _ i d ) :  
         d e v i c e   =   g e t _ o b j e c t _ o r _ 4 0 4 ( M i k r o t i k D e v i c e ,   i d = d e v i c e _ i d )  
         a p i   =   M i k r o t i k A P I ( d e v i c e )  
          
         s e c r e t s   =   a p i . g e t _ p p p _ s e c r e t s ( )  
         p r o f i l e s   =   a p i . g e t _ p p p _ p r o f i l e s ( )  
         a c t i v e _ u s e r s   =   a p i . g e t _ a c t i v e _ p p p o e _ u s e r s ( )  
          
         c o n t e x t   =   {  
                 ' d e v i c e ' :   d e v i c e ,  
                 ' s e c r e t s ' :   s e c r e t s ,  
                 ' p r o f i l e s ' :   p r o f i l e s ,  
                 ' a c t i v e _ u s e r s ' :   a c t i v e _ u s e r s ,  
                 ' a c t i v e _ t a b ' :   r e q u e s t . G E T . g e t ( ' t a b ' ,   ' s e c r e t s ' )  
         }  
         r e t u r n   r e n d e r ( r e q u e s t ,   ' n e t w o r k _ m a n a g e r / w i n b o x _ d a s h b o a r d . h t m l ' ,   c o n t e x t )  
  
  
 @ r o l e _ r e q u i r e d ( [ ' A d m i n ' ,   ' T e c h n i c i a n ' ,   ' C S R ' ] )  
 @ l o g i n _ r e q u i r e d  
 d e f   w i n b o x _ s e c r e t _ a c t i o n ( r e q u e s t ,   d e v i c e _ i d ) :  
         i f   r e q u e s t . m e t h o d   = =   ' P O S T ' :  
                 d e v i c e   =   g e t _ o b j e c t _ o r _ 4 0 4 ( M i k r o t i k D e v i c e ,   i d = d e v i c e _ i d )  
                 a p i   =   M i k r o t i k A P I ( d e v i c e )  
                 a c t i o n   =   r e q u e s t . P O S T . g e t ( ' a c t i o n ' )  
                  
                 i f   a c t i o n   = =   ' a d d ' :  
                         s u c c e s s ,   m s g   =   a p i . a d d _ p p p o e _ u s e r (  
                                 r e q u e s t . P O S T . g e t ( ' n a m e ' ) ,  
                                 r e q u e s t . P O S T . g e t ( ' p a s s w o r d ' ) ,  
                                 r e q u e s t . P O S T . g e t ( ' p r o f i l e ' ) ,  
                                 r e q u e s t . P O S T . g e t ( ' s e r v i c e ' ,   ' p p p o e ' ) ,  
                                 r e q u e s t . P O S T . g e t ( ' c o m m e n t ' ,   ' ' ) ,  
                                 d i s a b l e d = r e q u e s t . P O S T . g e t ( ' d i s a b l e d ' )   = =   ' o n '  
                         )  
                         i f   s u c c e s s :  
                                 m e s s a g e s . s u c c e s s ( r e q u e s t ,   f " S e c r e t   a d d e d :   { m s g } " )  
                         e l s e :  
                                 m e s s a g e s . e r r o r ( r e q u e s t ,   f " E r r o r   a d d i n g   s e c r e t :   { m s g } " )  
                                  
                 e l i f   a c t i o n   = =   ' e d i t ' :  
                         i n t e r n a l _ i d   =   r e q u e s t . P O S T . g e t ( ' i d ' )  
                         s u c c e s s ,   m s g   =   a p i . u p d a t e _ p p p _ s e c r e t (  
                                 i n t e r n a l _ i d ,  
                                 n a m e = r e q u e s t . P O S T . g e t ( ' n a m e ' ) ,  
                                 p a s s w o r d = r e q u e s t . P O S T . g e t ( ' p a s s w o r d ' ) ,  
                                 p r o f i l e = r e q u e s t . P O S T . g e t ( ' p r o f i l e ' ) ,  
                                 s e r v i c e = r e q u e s t . P O S T . g e t ( ' s e r v i c e ' ,   ' p p p o e ' ) ,  
                                 c o m m e n t = r e q u e s t . P O S T . g e t ( ' c o m m e n t ' ,   ' ' ) ,  
                                 d i s a b l e d = ' t r u e '   i f   r e q u e s t . P O S T . g e t ( ' d i s a b l e d ' )   = =   ' o n '   e l s e   ' f a l s e '  
                         )  
                         i f   s u c c e s s :  
                                 m e s s a g e s . s u c c e s s ( r e q u e s t ,   f " S e c r e t   u p d a t e d :   { m s g } " )  
                         e l s e :  
                                 m e s s a g e s . e r r o r ( r e q u e s t ,   f " E r r o r   u p d a t i n g   s e c r e t :   { m s g } " )  
                                  
                 e l i f   a c t i o n   = =   ' d e l e t e ' :  
                         i n t e r n a l _ i d   =   r e q u e s t . P O S T . g e t ( ' i d ' )  
                         s u c c e s s ,   m s g   =   a p i . d e l e t e _ p p p _ s e c r e t ( i n t e r n a l _ i d )  
                         i f   s u c c e s s :  
                                 m e s s a g e s . s u c c e s s ( r e q u e s t ,   f " S e c r e t   d e l e t e d :   { m s g } " )  
                         e l s e :  
                                 m e s s a g e s . e r r o r ( r e q u e s t ,   f " E r r o r   d e l e t i n g   s e c r e t :   { m s g } " )  
                                  
         r e t u r n   r e d i r e c t ( f " / n e t w o r k - m a n a g e r / w i n b o x / { d e v i c e _ i d } / ? t a b = s e c r e t s " )  
  
  
 @ r o l e _ r e q u i r e d ( [ ' A d m i n ' ,   ' T e c h n i c i a n ' ,   ' C S R ' ] )  
 @ l o g i n _ r e q u i r e d  
 d e f   w i n b o x _ p r o f i l e _ a c t i o n ( r e q u e s t ,   d e v i c e _ i d ) :  
         i f   r e q u e s t . m e t h o d   = =   ' P O S T ' :  
                 d e v i c e   =   g e t _ o b j e c t _ o r _ 4 0 4 ( M i k r o t i k D e v i c e ,   i d = d e v i c e _ i d )  
                 a p i   =   M i k r o t i k A P I ( d e v i c e )  
                 a c t i o n   =   r e q u e s t . P O S T . g e t ( ' a c t i o n ' )  
                  
                 #   B u i l d   k w a r g s   f r o m   f o r m ,   i g n o r i n g   e m p t y   o n e s   e x c e p t   n a m e  
                 k w a r g s   =   {  
                         ' n a m e ' :   r e q u e s t . P O S T . g e t ( ' n a m e ' ) ,  
                         ' l o c a l - a d d r e s s ' :   r e q u e s t . P O S T . g e t ( ' l o c a l _ a d d r e s s ' ,   ' ' ) ,  
                         ' r e m o t e - a d d r e s s ' :   r e q u e s t . P O S T . g e t ( ' r e m o t e _ a d d r e s s ' ,   ' ' ) ,  
                         ' r a t e - l i m i t ' :   r e q u e s t . P O S T . g e t ( ' r a t e _ l i m i t ' ,   ' ' )  
                 }  
                 #   R e m o v e   e m p t y   s t r i n g   k w a r g s   s o   R o u t e r O S   d e f a u l t s   t a k e   o v e r  
                 k w a r g s   =   { k :   v   f o r   k ,   v   i n   k w a r g s . i t e m s ( )   i f   v }  
                  
                 i f   a c t i o n   = =   ' a d d ' :  
                         s u c c e s s ,   m s g   =   a p i . a d d _ p p p _ p r o f i l e ( * * k w a r g s )  
                         i f   s u c c e s s :  
                                 m e s s a g e s . s u c c e s s ( r e q u e s t ,   f " P r o f i l e   a d d e d :   { m s g } " )  
                         e l s e :  
                                 m e s s a g e s . e r r o r ( r e q u e s t ,   f " E r r o r   a d d i n g   p r o f i l e :   { m s g } " )  
                                  
                 e l i f   a c t i o n   = =   ' e d i t ' :  
                         i n t e r n a l _ i d   =   r e q u e s t . P O S T . g e t ( ' i d ' )  
                         s u c c e s s ,   m s g   =   a p i . u p d a t e _ p p p _ p r o f i l e ( i n t e r n a l _ i d ,   * * k w a r g s )  
                         i f   s u c c e s s :  
                                 m e s s a g e s . s u c c e s s ( r e q u e s t ,   f " P r o f i l e   u p d a t e d :   { m s g } " )  
                         e l s e :  
                                 m e s s a g e s . e r r o r ( r e q u e s t ,   f " E r r o r   u p d a t i n g   p r o f i l e :   { m s g } " )  
                                  
                 e l i f   a c t i o n   = =   ' d e l e t e ' :  
                         i n t e r n a l _ i d   =   r e q u e s t . P O S T . g e t ( ' i d ' )  
                         s u c c e s s ,   m s g   =   a p i . d e l e t e _ p p p _ p r o f i l e ( i n t e r n a l _ i d )  
                         i f   s u c c e s s :  
                                 m e s s a g e s . s u c c e s s ( r e q u e s t ,   f " P r o f i l e   d e l e t e d :   { m s g } " )  
                         e l s e :  
                                 m e s s a g e s . e r r o r ( r e q u e s t ,   f " E r r o r   d e l e t i n g   p r o f i l e :   { m s g } " )  
                                  
         r e t u r n   r e d i r e c t ( f " / n e t w o r k - m a n a g e r / w i n b o x / { d e v i c e _ i d } / ? t a b = p r o f i l e s " )  
  
  
 @ r o l e _ r e q u i r e d ( [ ' A d m i n ' ,   ' T e c h n i c i a n ' ,   ' C S R ' ] )  
 @ l o g i n _ r e q u i r e d  
 d e f   w i n b o x _ k i c k _ a c t i o n ( r e q u e s t ,   d e v i c e _ i d ) :  
         i f   r e q u e s t . m e t h o d   = =   ' P O S T ' :  
                 d e v i c e   =   g e t _ o b j e c t _ o r _ 4 0 4 ( M i k r o t i k D e v i c e ,   i d = d e v i c e _ i d )  
                 a p i   =   M i k r o t i k A P I ( d e v i c e )  
                 u s e r n a m e   =   r e q u e s t . P O S T . g e t ( ' u s e r n a m e ' )  
                 s u c c e s s ,   m s g   =   a p i . k i c k _ a c t i v e _ u s e r ( u s e r n a m e )  
                 i f   s u c c e s s :  
                         m e s s a g e s . s u c c e s s ( r e q u e s t ,   f " K i c k e d   u s e r   { u s e r n a m e } :   { m s g } " )  
                 e l s e :  
                         m e s s a g e s . e r r o r ( r e q u e s t ,   f " E r r o r   k i c k i n g   u s e r :   { m s g } " )  
                          
         r e t u r n   r e d i r e c t ( f " / n e t w o r k - m a n a g e r / w i n b o x / { d e v i c e _ i d } / ? t a b = a c t i v e " )  
 