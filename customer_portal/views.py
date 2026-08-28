from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from billing.models import Customer, Payment, SubscriptionPlan, Notification, AddOnRequest
from billing.views import calculate_new_expiration_date
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

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
        
    if customer.must_change_password:
        return redirect('customer_portal:force_change_password')
        
    plan = customer.plan
    payments = Payment.objects.filter(customer=customer).order_by('-created_at')[:10]
    plans = SubscriptionPlan.objects.all().order_by('price')
    
    effective_status = 'Excellent'
    effective_reason = 'Your service is running normally.'
    is_network_issue = False

    def get_priority(status):
        priorities = {'Excellent': 0, 'Active': 0, 'Good': 0, 'Moderate': 1, 'Maintenance': 1, 'Poor': 2, 'Disconnected': 2, 'Offline': 3, 'Outage': 4}
        return priorities.get(status, 0)

    if customer.health_status and get_priority(customer.health_status) > get_priority(effective_status):
        effective_status = customer.health_status
        effective_reason = customer.health_reason or "We have detected an issue with your connection."
        is_network_issue = True

    if customer.barangay and get_priority(customer.barangay.health_status) > get_priority(effective_status):
        effective_status = customer.barangay.health_status
        effective_reason = customer.barangay.health_reason or f"Network issue reported in {customer.barangay.name}"
        is_network_issue = True

    if customer.mikrotik_device and get_priority(customer.mikrotik_device.health_status) > get_priority(effective_status):
        effective_status = customer.mikrotik_device.health_status
        effective_reason = customer.mikrotik_device.health_reason or "Network issue reported for your sector"
        is_network_issue = True
    
    if customer.status in ['suspended', 'expired', 'inactive']:
        effective_status = 'Disconnected'
        effective_reason = "Your account has been suspended due to an overdue balance. Please pay your bill to restore connection."
        is_network_issue = True
        
    is_expiring_soon = False
    if customer.expires_at and customer.status == 'active':
        if customer.expires_at <= timezone.now() + timedelta(days=3):
            is_expiring_soon = True
        
    context = {
        'customer': customer,
        'plan': plan,
        'effective_status': effective_status,
        'effective_reason': effective_reason,
        'is_network_issue': is_network_issue,
        'is_expiring_soon': is_expiring_soon,
        'payments': payments,
        'plans': plans
    }
    return render(request, 'customer_portal/portal_dashboard.html', context)


def portal_statement_view(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('login')
        
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect('login')
        
    if customer.must_change_password:
        return redirect('customer_portal:force_change_password')
        
    payments = Payment.objects.filter(customer=customer).order_by('-created_at')
    
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    
    if date_from and date_to:
        payments = payments.filter(paid_at__date__gte=date_from, paid_at__date__lte=date_to)
        
    total_paid = sum(p.amount for p in payments)
    
    context = {
        'customer': customer,
        'payments': payments,
        'date_from': date_from,
        'date_to': date_to,
        'total_paid': total_paid,
    }
    return render(request, 'customer_portal/portal_statement.html', context)

def portal_logout(request):
    request.session.flush()
    return redirect('login')

def force_change_password(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('login')
        
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect('login')
        
    if not customer.must_change_password:
        return redirect('customer_portal:portal_dashboard')
        
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not new_password or not confirm_password:
            messages.error(request, "Please fill in all fields.")
        elif len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
        elif new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
        else:
            customer.portal_password = new_password
            customer.must_change_password = False
            customer.save()
            messages.success(request, "Password updated successfully! Welcome to your dashboard.")
            return redirect('customer_portal:portal_dashboard')
            
    return render(request, 'customer_portal/force_change_password.html', {'customer': customer})

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


def portal_process_mock_payment(request):
    if request.method == 'POST':
        customer_id = request.session.get('customer_id')
        if not customer_id:
            return redirect('login')
            
        amount = request.POST.get('amount')
        plan_id = request.POST.get('plan_id')
        payment_method = request.POST.get('payment_method', 'Customer Portal (Mock)')
        
        if amount:
            try:
                amount_float = float(amount)
                customer = Customer.objects.get(id=customer_id)
                monthly_price = float(customer.plan.price) if customer.plan else 0.0
                
                with transaction.atomic():
                    # Lock for update
                    locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)
                    was_suspended = locked_customer.status in ['suspended', 'inactive', 'expired']
                    
                    old_plan_id = str(locked_customer.plan_id)
                    is_upgrade = False
                    is_downgrade = False
                    if plan_id and old_plan_id != str(plan_id):
                        new_plan = SubscriptionPlan.objects.get(id=plan_id)
                        old_price = float(locked_customer.plan.price) if locked_customer.plan else 0.0
                        monthly_price = float(new_plan.price)
                        
                        if monthly_price < old_price:
                            raise Exception("Plan downgrades cannot be processed online. Please contact Gametech support.")
                            
                        locked_customer.plan = new_plan
                        if monthly_price > old_price:
                            is_upgrade = True
                        else:
                            is_downgrade = True
                        
                    if locked_customer.expires_at and locked_customer.expires_at > timezone.now():
                        current_exp = locked_customer.expires_at
                    else:
                        current_exp = timezone.now()
                        
                    new_expiry = calculate_new_expiration_date(current_exp, amount_float, monthly_price)
                    
                    # Update DB
                    locked_customer.expires_at = new_expiry
                    locked_customer.outstanding_balance -= Decimal(amount)
                    
                    if was_suspended:
                        locked_customer.status = 'active'
                        
                    locked_customer.save()
                    
                    # Log Payment as Customer Portal
                    reference = f"PORTAL-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                    Payment.objects.create(
                        customer=locked_customer,
                        username=locked_customer.pppoe_username,
                        plan_name=locked_customer.plan.name if locked_customer.plan else None,
                        amount=amount,
                        payment_method=payment_method,
                        reference_no=reference,
                        reason="Online Payment",
                        expires_at=new_expiry,
                        adjusted_by="Customer Portal"
                    )
                    
                # Mikrotik Activation
                if customer.mikrotik_device:
                    try:
                        from network_manager.services import MikrotikAPI
                        api = MikrotikAPI(customer.mikrotik_device)
                        
                        # Mikrotik Format: paid (date) exp (date) . plan . method . admin
                        expiry_str = new_expiry.strftime('%b %d, %Y')
                        paid_str = timezone.now().strftime('%b %d, %Y')
                        plan_name = customer.plan.name if customer.plan else "No Plan"
                        comment_text = f"paid {paid_str} exp {expiry_str} . {plan_name} . {payment_method} . Customer Portal . Paid Online"
                        api.set_pppoe_comment(customer.pppoe_username, comment_text)
                        
                        # The post_save signal on Customer handles setting the profile, enabling, and kicking the user.
                        # We only need to manually update the comment here to record the payment details.
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to sync portal renewal for {customer.pppoe_username}: {e}")
                
                # Build Message
                base_msg = f"Payment of ₱{amount} via {payment_method} successful! Your account is now active until {new_expiry.strftime('%b %d, %Y')}."
                if is_upgrade:
                    base_msg += f" Thank you for upgrading to {new_plan.name}! Enjoy your faster speeds."
                elif is_downgrade:
                    base_msg += f" Your plan has been successfully updated to {new_plan.name}. If you wish to upgrade soon for faster speeds, you can always do so!"

                from django.urls import reverse
                customer_url = reverse('view_customer', args=[customer.id])
                
                Notification.objects.create(
                    title="Portal Payment Received",
                    message=f"{customer.full_name} paid ₱{amount} via {payment_method}.",
                    notification_type="payment",
                    link=customer_url
                )
                
                if is_upgrade:
                    Notification.objects.create(
                        title="Plan Upgrade",
                        message=f"{customer.full_name} upgraded their plan to {new_plan.name} via the portal.",
                        notification_type="system",
                        link=customer_url
                    )

                messages.success(request, base_msg)
            except Exception as e:
                messages.error(request, f"Payment processing failed: {e}")
                
    return redirect('customer_portal:portal_dashboard')

def portal_apply_addon(request):
    if request.method == 'POST':
        customer_id = request.session.get('customer_id')
        if not customer_id:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
            
        import json
        try:
            data = json.loads(request.body)
            addon_type = data.get('addon_type')
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)
            
        if not addon_type:
            return JsonResponse({'status': 'error', 'message': 'Addon type is required'}, status=400)
            
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Customer not found'}, status=404)
            
        from billing.models import AddOnRequest
        AddOnRequest.objects.create(
            customer=customer,
            addon_type=addon_type,
            status='Pending'
        )
        
        from django.urls import reverse
        customer_url = reverse('view_customer', args=[customer.id])
        
        Notification.objects.create(
            title=f"New Add-on Request: {addon_type}",
            message=f"{customer.full_name} has requested {addon_type}. Please contact them.",
            notification_type="cignal",
            link=customer_url
        )
        
        return JsonResponse({'status': 'success', 'message': 'Request submitted successfully. Our staff will contact you soon.'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
