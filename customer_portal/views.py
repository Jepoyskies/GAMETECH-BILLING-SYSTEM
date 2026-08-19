from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from billing.models import Customer, Payment

def portal_login(request):
    # If already logged in, redirect to dashboard
    if request.session.get('customer_id'):
        return redirect('customer_portal:portal_dashboard')

    if request.method == 'POST':
        pppoe_username = request.POST.get('pppoe_username')
        pppoe_password = request.POST.get('pppoe_password')
        
        try:
            customer = Customer.objects.get(pppoe_username=pppoe_username, pppoe_password=pppoe_password)
            request.session['customer_id'] = customer.id
            return redirect('customer_portal:portal_dashboard')
        except Customer.DoesNotExist:
            messages.error(request, 'Invalid PPPoE username or password.')
            
    return render(request, 'customer_portal/portal_login.html')

def portal_dashboard(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('login')
        
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect('login')
        
    plan = customer.plan
    payments = Payment.objects.filter(customer=customer).order_by('-created_at')[:10]
    
    context = {
        'customer': customer,
        'plan': plan,
        'payments': payments,
    }
    return render(request, 'customer_portal/portal_dashboard.html', context)

def portal_logout(request):
    request.session.flush()
    return redirect('login')

def portal_router_uplink_api(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
        
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Customer not found'}, status=404)
        
    if not customer.mikrotik_device:
        return JsonResponse({'status': 'error', 'message': 'No router assigned'})
        
    device = customer.mikrotik_device
    try:
        from network_manager.services import MikrotikAPI
        api = MikrotikAPI(device)
        api_conn = api._get_api()
        
        # Get System Resources (CPU, Memory, Uptime)
        resource_data = api_conn.get_resource('/system/resource').get()[0]
        
        # Ping test for uplink status
        uplink_status = 'Offline'
        uplink_ping = 'Timeout'
        try:
            ping_res = api_conn.get_resource('/').call('ping', {'address': '8.8.8.8', 'count': '1'})
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
                    if rtt_ms > 150:
                        uplink_status = 'Unstable'
                    else:
                        uplink_status = 'Online'
        except Exception:
            pass
        
        # Get Routerboard info for temperature/voltage (if supported)
        health_data = []
        try:
            health_data = api_conn.get_resource('/system/health').get()
        except Exception:
            pass # Not all routers support /system/health

        api.connection.disconnect()
        
        # Get optical readings via wrapper
        optical_data = api.get_optical_readings()
        
        return JsonResponse({
            'status': 'success',
            'resource': resource_data,
            'health': health_data,
            'optical': optical_data,
            'uplink_status': uplink_status,
            'uplink_ping': uplink_ping
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
