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
@require_POST
def bulk_sms_view(request):
    import json
    import time
    try:
        data = json.loads(request.body)
        customer_ids = data.get('customer_ids', [])
        message = data.get('message', '').strip()

        if not customer_ids or not message:
            return JsonResponse({'success': False, 'error': 'Missing customers or message.'})

        customers = Customer.objects.filter(id__in=customer_ids)
        sent_count = 0

        for customer in customers:
            if customer.phone:
                response, is_success = send_semaphore_sms(customer.phone, message)
                if is_success:
                    sent_count += 1
                time.sleep(0.1)  # Prevent rate limiting

        return JsonResponse({'success': True, 'sent_count': sent_count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def bulk_email_view(request):
    import json
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        data = json.loads(request.body)
        customer_ids = data.get('customer_ids', [])
        subject = data.get('subject', 'Important Notice').strip()
        message = data.get('message', '').strip()

        if not customer_ids or not message:
            return JsonResponse({'success': False, 'error': 'Missing customers or message.'})

        customers = Customer.objects.filter(id__in=customer_ids)
        sent_count = 0
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@gametech.com')

        for customer in customers:
            if customer.email:
                try:
                    send_mail(
                        subject,
                        message,
                        from_email,
                        [customer.email],
                        fail_silently=False,
                    )
                    sent_count += 1
                except Exception as e:
                    print(f"Failed to send email to {customer.email}: {e}")

        return JsonResponse({'success': True, 'sent_count': sent_count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def customer_list(request):
    from network_manager.models import MikrotikDevice
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Case, When, Value, IntegerField
    
    customers = Customer.objects.select_related(
        'plan', 'agent', 'barangay', 'mikrotik_device').all()
        
    filter_type = request.GET.get('filter', 'all')
    
    now = timezone.now()
    seven_days_from_now = now + timedelta(days=7)
    seven_days_ago = now - timedelta(days=7)
    
    if filter_type == 'active':
        customers = customers.filter(expires_at__gt=seven_days_from_now, status='active')
    elif filter_type == 'expiring':
        customers = customers.filter(expires_at__gt=now, expires_at__lte=seven_days_from_now, status='active')
    elif filter_type == 'expired':
        customers = customers.filter(expires_at__lte=now, expires_at__gt=seven_days_ago)
    elif filter_type == 'inactive':
        customers = customers.filter(expires_at__lte=seven_days_ago)
        
    customers = customers.annotate(
        status_order=Case(
            When(status='active', then=Value(1)),
            When(status='pending', then=Value(2)),
            When(status='suspended', then=Value(3)),
            When(status='expired', then=Value(4)),
            When(status='inactive', then=Value(5)),
            When(status='pull out', then=Value(6)),
            default=Value(7),
            output_field=IntegerField(),
        )
    ).order_by('status_order', 'full_name')
        
    devices = MikrotikDevice.objects.all().order_by('device_name')
    from ..models import Barangay
    barangays = Barangay.objects.all().order_by('name')
    return render(request, 'billing/customer_list.html', {
        'customers': customers,
        'devices': devices,
        'barangays': barangays,
        'filter_type': filter_type
    })


@login_required
@role_required(['Admin', 'Agent', 'CSR'])
@permission_required('billing.add_customer', raise_exception=True)
def add_customer(request):
    if request.method == 'POST':
        from django.utils.crypto import get_random_string
        if request.user.role == 'Agent':
            barangay_name = request.POST.get('barangay_name')
            if barangay_name:
                barangay, _ = Barangay.objects.get_or_create(
                    name__iexact=barangay_name, 
                    defaults={'name': barangay_name, 'health_status': 'Excellent'}
                )
                barangay_id = barangay.id
            else:
                barangay_id = None
            latitude = None
            longitude = None
        else:
            barangay_id = request.POST.get('barangay_id')
            latitude = request.POST.get('latitude') or None
            longitude = request.POST.get('longitude') or None

        customer = Customer.objects.create(
            full_name=request.POST.get('full_name'),
            email=request.POST.get('email') or None,
            phone=request.POST.get('phone'),
            address=request.POST.get('address'),
            pppoe_username=request.POST.get('pppoe_username') or None,
            pppoe_password=request.POST.get('pppoe_password') or get_random_string(8),
            status='pending' if request.user.role == 'Agent' else request.POST.get('status', 'active'),
            plan_id=request.POST.get('plan_id'),
            mikrotik_device_id=request.POST.get('device_id') or None,
            agent_id=request.POST.get('agent_id'),
            barangay_id=barangay_id,
            account_type_id=request.POST.get('account_type_id') or None,
            latitude=latitude,
            longitude=longitude,
            cignalplay_no=request.POST.get('cignalplay_no'),
            cignalplay_date=request.POST.get('cignalplay_date') or None,
            created_form_by=request.user.username
        )
        
        from ..models import SystemLog
        SystemLog.objects.create(
            table_name='Customer',
            record_id=str(customer.id),
            action='ADD',
            changed_by=request.user.username,
            target_name=customer.full_name,
            old_data="",
            new_data=f"Name: {customer.full_name}\nPhone: {customer.phone}\nStatus: {customer.status}"
        )
        messages.success(request, 'Customer added successfully!')
        return redirect('customer_list')
    context = {
        'categorized_plans': get_categorized_plans(),
        'devices': MikrotikDevice.objects.all(),
        'agents': Agent.objects.all(),
        'barangays': Barangay.objects.all(),
        'account_types': AccountType.objects.all(),
        'prefill_username': request.GET.get('pppoe_username', '')
    }
    return render(request, 'billing/add_customer.html', context)


@role_required(['Admin', 'Editor'])
@login_required
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        old_data = []
        new_data = []

        def check_change(field_name, old_val, new_val):
            # Treat None and empty string as equivalent for logging
            if (old_val or "") != (new_val or ""):
                old_data.append(f"{field_name}: {old_val}")
                new_data.append(f"{field_name}: {new_val}")

        check_change('Name', customer.full_name, request.POST.get('full_name'))
        customer.full_name = request.POST.get('full_name')

        check_change('Email', customer.email, request.POST.get('email'))
        customer.email = request.POST.get('email') or None

        check_change('Phone', customer.phone, request.POST.get('phone'))
        customer.phone = request.POST.get('phone')

        check_change('Address', customer.address, request.POST.get('address'))
        customer.address = request.POST.get('address')

        check_change('PPPoE Username', customer.pppoe_username, request.POST.get('pppoe_username'))
        customer.pppoe_username = request.POST.get('pppoe_username') or None
        
        new_password = request.POST.get('pppoe_password')
        if new_password:
            check_change('PPPoE Password', '***', '*** (changed)')
            customer.pppoe_password = new_password
        elif not customer.pppoe_password:
            from django.utils.crypto import get_random_string
            customer.pppoe_password = get_random_string(8)
            check_change('PPPoE Password', 'None', '*** (auto-generated)')
            
        check_change('Status', customer.status, request.POST.get('status', 'active'))
        customer.status = request.POST.get('status', 'active')
        
        # Handle ForeignKeys (using _id allows us to assign None if empty string, or the ID directly)
        plan_id = request.POST.get('plan_id')
        if str(customer.plan_id or "") != str(plan_id or ""):
            old_data.append(f"Plan ID: {customer.plan_id}")
            new_data.append(f"Plan ID: {plan_id}")
        customer.plan_id = plan_id if plan_id else None
        
        device_id = request.POST.get('device_id')
        if str(customer.mikrotik_device_id or "") != str(device_id or ""):
            old_data.append(f"Device ID: {customer.mikrotik_device_id}")
            new_data.append(f"Device ID: {device_id}")
        customer.mikrotik_device_id = device_id if device_id else None
        
        if request.POST.get('is_verified') == 'True':
            if not customer.is_verified:
                old_data.append('is_verified: False')
                new_data.append('is_verified: True')
                customer.is_verified = True
        
        agent_id = request.POST.get('agent_id')
        if str(customer.agent_id or "") != str(agent_id or ""):
            old_data.append(f"Agent ID: {customer.agent_id}")
            new_data.append(f"Agent ID: {agent_id}")
        customer.agent_id = agent_id if agent_id else None
        
        if request.user.role == 'Agent':
            barangay_name = request.POST.get('barangay_name')
            if barangay_name:
                barangay, _ = Barangay.objects.get_or_create(
                    name__iexact=barangay_name, 
                    defaults={'name': barangay_name, 'health_status': 'Excellent'}
                )
                if str(customer.barangay_id or "") != str(barangay.id):
                    old_data.append(f"Barangay ID: {customer.barangay_id}")
                    new_data.append(f"Barangay ID: {barangay.id}")
                customer.barangay_id = barangay.id
            else:
                if customer.barangay_id is not None:
                    old_data.append(f"Barangay ID: {customer.barangay_id}")
                    new_data.append(f"Barangay ID: None")
                customer.barangay_id = None
        else:
            barangay_id = request.POST.get('barangay_id')
            if str(customer.barangay_id or "") != str(barangay_id or ""):
                old_data.append(f"Barangay ID: {customer.barangay_id}")
                new_data.append(f"Barangay ID: {barangay_id}")
            customer.barangay_id = barangay_id if barangay_id else None
        
        account_type_id = request.POST.get('account_type_id')
        if str(customer.account_type_id or "") != str(account_type_id or ""):
            old_data.append(f"Account Type ID: {customer.account_type_id}")
            new_data.append(f"Account Type ID: {account_type_id}")
        customer.account_type_id = account_type_id if account_type_id else None
        
        if request.user.role != 'Agent':
            latitude = request.POST.get('latitude')
            if latitude:
                check_change('Latitude', customer.latitude, latitude)
                customer.latitude = latitude
            longitude = request.POST.get('longitude')
            if longitude:
                check_change('Longitude', customer.longitude, longitude)
                customer.longitude = longitude
        
        # Cignal Play Integration
        check_change('Cignal Play No', customer.cignalplay_no, request.POST.get('cignalplay_no'))
        customer.cignalplay_no = request.POST.get('cignalplay_no')
        
        cignal_date = request.POST.get('cignalplay_date')
        if cignal_date:
            check_change('Cignal Play Date', str(customer.cignalplay_date) if customer.cignalplay_date else None, cignal_date)
            customer.cignalplay_date = cignal_date
            
        check_change('Health Status', customer.health_status, request.POST.get('health_status', 'Excellent'))
        customer.health_status = request.POST.get('health_status', 'Excellent')

        check_change('Health Reason', customer.health_reason, request.POST.get('health_reason'))
        customer.health_reason = request.POST.get('health_reason')
            
        if old_data or new_data:
            from ..models import SystemLog
            SystemLog.objects.create(
                table_name='Customer',
                record_id=str(customer.id),
                action='UPDATE',
                changed_by=request.user.username,
                target_name=customer.full_name,
                old_data='\n'.join(old_data),
                new_data='\n'.join(new_data)
            )

        customer.save()
        messages.success(request, f'Customer {customer.full_name} updated successfully!')
        return redirect('view_customer', customer_id=customer.id)

    context = {
        'customer': customer,
        'categorized_plans': get_categorized_plans(),
        'devices': MikrotikDevice.objects.all(),
        'agents': Agent.objects.all(),
        'barangays': Barangay.objects.all(),
        'account_types': AccountType.objects.all()
    }
    return render(request, 'billing/edit_customer.html', context)


@login_required
def view_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    payments = customer.payments.all().order_by('-paid_at')
    
    # Try to fetch live MT connection status if they have a router
    mt_status = "Loading..."
    uptime = "Loading..."
    live_mac = "Loading..."
    last_logged_out = "Loading..."
    
    from ..models import SystemLog, Payment, AuditLog, AddOnRequest, CignalPlay
    
    # Combine logs
    all_logs = []
    
    # 1. System Logs
    sys_logs = SystemLog.objects.filter(record_id=str(customer.id), table_name='Customer').order_by('-changed_at')
    for log in sys_logs:
        all_logs.append({
            'type': 'system',
            'date': log.changed_at,
            'title': f"Profile {log.action}",
            'details': log.new_data,
            'user': log.changed_by
        })
        
    # 2. Payments
    for p in payments:
        all_logs.append({
            'type': 'payment',
            'date': p.created_at,
            'title': f"Payment: ₱{p.amount}",
            'details': f"Method: {p.payment_method}",
            'user': 'System'
        })
        
    # 3. Add-ons / Cignal Play
    addons = AddOnRequest.objects.filter(customer=customer)
    for a in addons:
        all_logs.append({
            'type': 'addon',
            'date': a.requested_at,
            'title': f"Add-on: {a.addon_type}",
            'details': f"Status: {a.status}",
            'user': 'Customer/System'
        })
        
    # 4. Audit Logs (force reactivations etc)
    audit_logs = AuditLog.objects.filter(customer=customer)
    for al in audit_logs:
        all_logs.append({
            'type': 'audit',
            'date': al.timestamp,
            'title': f"Action: {al.action_type}",
            'details': al.remarks,
            'user': al.admin_user.username if al.admin_user else 'System'
        })
        
    # Sort all logs by date descending
    all_logs.sort(key=lambda x: x['date'], reverse=True)
            
    context = {
        'customer': customer,
        'payments': payments,
        'all_logs': all_logs,
        'mt_status': mt_status,
        'uptime': uptime,
        'live_mac': live_mac,
        'last_logged_out': last_logged_out,
    }
    return render(request, 'billing/view_customer.html', context)


@login_required
@role_required(['Admin'])
def edit_customer_expiration(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        new_date_str = request.POST.get('expires_at')
        if new_date_str:
            from django.utils.dateparse import parse_datetime
            from ..models import SystemLog
            new_date = parse_datetime(new_date_str)
            if new_date:
                old_date = customer.expires_at.strftime("%Y-%m-%d %H:%M:%S") if customer.expires_at else "None"
                customer.expires_at = new_date
                customer.save()
                SystemLog.objects.create(
                    table_name='Customer',
                    record_id=str(customer.id),
                    action='UPDATE',
                    changed_by=request.user.username,
                    old_data=f"Expiration: {old_date}",
                    new_data=f"Expiration: {new_date.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                messages.success(request, f"Expiration date for {customer.full_name} has been successfully updated.")
            else:
                messages.error(request, "Invalid date format.")
    return redirect('view_customer', customer_id=customer.id)


@login_required
@role_required(['Admin'])
def edit_customer_balance(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        new_balance_str = request.POST.get('outstanding_balance')
        if new_balance_str is not None:
            try:
                from decimal import Decimal
                from ..models import SystemLog
                new_balance = Decimal(new_balance_str)
                old_balance = customer.outstanding_balance
                customer.outstanding_balance = new_balance
                customer.save()
                SystemLog.objects.create(
                    table_name='Customer',
                    record_id=str(customer.id),
                    action='UPDATE',
                    changed_by=request.user.username,
                    target_name=customer.full_name,
                    old_data=f"Balance: ₱{old_balance}",
                    new_data=f"Balance: ₱{new_balance}"
                )
                messages.success(request, f"Balance for {customer.full_name} has been successfully updated.")
            except:
                messages.error(request, "Invalid balance amount.")
    return redirect('view_customer', customer_id=customer.id)


@login_required
@role_required(['Admin', 'Editor'])
@permission_required('billing.delete_customer', raise_exception=True)
def delete_customer(request, customer_id):
    if request.method == 'POST':
        customer = get_object_or_404(Customer, id=customer_id)
        name = customer.full_name
        customer.delete()
        messages.success(request, f'Customer {name} deleted successfully!')
    return redirect('customer_list')


@login_required
@permission_required('billing.change_customer', raise_exception=True)
def customer_force_suspend(request, username):
    """Manually force suspends a customer (updates profile, kicks session, and updates DB status)"""
    if request.method == 'POST':
        customer = get_object_or_404(Customer, pppoe_username=username)
        if customer.mikrotik_device:
            from network_manager.services import MikrotikAPI
            api = MikrotikAPI(customer.mikrotik_device)
            success, msg = api.suspend_pppoe_user(username)
            if success:
                customer.status = 'suspended'
                customer.save()
                messages.success(request, f"Customer {username} has been forcefully suspended.")
            else:
                messages.error(request, f"Failed to suspend {username}: {msg}")
        else:
            messages.error(request, "Customer has no Mikrotik device assigned.")
        return redirect('view_customer', customer_id=customer.id)
    return redirect('customer_list')


@login_required
def customer_kick_session(request, username):
    """Manually kicks the active PPPoE session without altering their billing status"""
    if request.method == 'POST':
        customer = get_object_or_404(Customer, pppoe_username=username)
        if customer.mikrotik_device:
            from network_manager.services import MikrotikAPI
            api = MikrotikAPI(customer.mikrotik_device)
            success, msg = api.kick_active_user(username)
            if success:
                messages.success(request, f"Active session for {username} was kicked successfully.")
            else:
                messages.error(request, f"Failed to kick session for {username}: {msg}")
        else:
            messages.error(request, "Customer has no Mikrotik device assigned.")
        return redirect('view_customer', customer_id=customer.id)
    return redirect('customer_list')


@login_required
@permission_required('billing.change_customer', raise_exception=True)
def customer_force_reactivate(request, username):
    """Manually force reactivates a customer using Master Password and logs it to AuditLog"""
    if request.method == 'POST':
        import os
        admin_password = request.POST.get('admin_password', '')
        reason = request.POST.get('override_reason', '')
        customer = get_object_or_404(Customer, pppoe_username=username)
        
        # Verify that the user is a superuser and entered their correct password
        if not request.user.is_superuser or not request.user.check_password(admin_password):
            messages.error(request, "Admin Override Failed: Invalid Password or you are not a Superuser.")
            return redirect('view_customer', customer_id=customer.id)
            
        if not reason.strip():
            messages.error(request, "Admin Override Failed: Reason for override is required.")
            return redirect('view_customer', customer_id=customer.id)
            
        if customer.mikrotik_device:
            from network_manager.services import MikrotikAPI
            api = MikrotikAPI(customer.mikrotik_device)
            
            # Use their plan name as the profile, or "default" if no plan is assigned
            target_profile = customer.plan.name if customer.plan else "default"
            
            # 1. Enable User (removes bridge drop rule and enables ppp secret)
            enable_success, enable_msg = api.enable_pppoe_user(username)
            if enable_success:
                # 2. Update Profile
                prof_success, prof_msg = api.set_user_pppoe_profile(username, target_profile)
                if prof_success:
                    # 3. Kick Session (allows modem to redial and gain internet)
                    kick_success, kick_msg = api.kick_active_user(username)
                    
                    # 4. Update DB
                    customer.status = 'active'
                    # DO NOT update expiration date or outstanding balance
                    customer.save()
                    
                    # 5. Log the override in the new AuditLog model
                    from billing.models import AuditLog
                    AuditLog.objects.create(
                        admin_user=request.user if request.user.is_authenticated else None,
                        customer=customer,
                        action_type='FORCE_REACTIVATE',
                        remarks=reason
                    )
                    
                    messages.success(request, f"Customer {username} force-reactivated via Master Override.")
                else:
                    messages.error(request, f"Failed to restore profile for {username}: {prof_msg}")
            else:
                messages.error(request, f"Failed to enable user {username}: {enable_msg}")
        else:
            messages.error(request, "Customer has no Mikrotik device assigned.")
        return redirect('view_customer', customer_id=customer.id)
    return redirect('customer_list')


@login_required
def mac_history_view(request):
    from ..models import CustomerMacHistory
    history = CustomerMacHistory.objects.select_related('customer').all()
    search = request.GET.get('search', '').strip()
    if search:
        history = history.filter(
            Q(customer__full_name__icontains=search) |
            Q(mac_address__icontains=search) |
            Q(customer__id__icontains=search)
        )
    return render(request, 'billing/mac_history.html', {'history': history})


@login_required
def sms_view(request):
    if request.method == 'POST':
        if 'send_sms_custom' in request.POST:
            phone = request.POST.get('phone')
            message = request.POST.get('message')
            
            response_text, is_success = send_semaphore_sms(phone, message)
            status = 'success' if is_success else 'error'
            
            SmsLog.objects.create(
                phone=phone,
                message=message,
                response=response_text,
                status=status
            )
            messages.info(request, f"SMS sent to {phone}. Response: {response_text}")
            
        elif 'bulk_send_sms' in request.POST:
            phones_str = request.POST.get('selected_phones', '')
            bulk_message = request.POST.get('bulk_message')
            phones = [p.strip() for p in phones_str.split(',') if p.strip()]
            
            for phone in phones:
                response_text, is_success = send_semaphore_sms(phone, bulk_message)
                status = 'success' if is_success else 'error'
                SmsLog.objects.create(
                    phone=phone,
                    message=bulk_message,
                    response=response_text,
                    status=status
                )
            messages.info(request, f"Bulk SMS sent to {len(phones)} recipients.")
            
        return redirect('sms_messaging')

    search = request.GET.get('search', '')
    customers = Customer.objects.exclude(username__isnull=True).exclude(username='')
    
    if search:
        customers = customers.filter(
            Q(username__icontains=search) |
            Q(full_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(address__icontains=search) |
            Q(status__icontains=search)
        )
    
    customers = customers.order_by('full_name')
    paginator = Paginator(customers, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    sms_logs = SmsLog.objects.all()[:100]
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'sms_logs': sms_logs
    }
    
    q = request.GET.copy()
    if 'page' in q:
        del q['page']
    context['query_params'] = q.urlencode()
    return render(request, 'billing/sms_messaging.html', context)


@login_required
def auto_suspend_view(request):
    if request.method == 'POST':
        usernames = request.POST.getlist('usernames')
        if not usernames:
            messages.error(request, 'No users selected for suspension.')
            return redirect('auto_suspend')
            
        suspended_count = 0
        errors = []
        
        # Group by device to minimize connections
        customers_to_suspend = Customer.objects.filter(username__in=usernames).select_related('mikrotik_device')
        device_users = {}
        for c in customers_to_suspend:
            if c.mikrotik_device:
                if c.mikrotik_device not in device_users:
                    device_users[c.mikrotik_device] = []
                device_users[c.mikrotik_device].append(c)
                
        for device, users in device_users.items():
            api = MikrotikAPI(device)
            for user in users:
                success, msg = api.suspend_pppoe_user(user.username)
                if success:
                    suspended_count += 1
                else:
                    errors.append(f"Failed to suspend {user.username}: {msg}")
                    
        if suspended_count > 0:
            messages.success(request, f'Successfully suspended {suspended_count} users.')
        if errors:
            for err in errors:
                messages.error(request, err)
                
        return redirect('auto_suspend')

    # GET request: fetch past due customers
    past_due_customers = Customer.objects.filter(
        expires_at__lte=timezone.now(),
        mikrotik_device__isnull=False
    ).exclude(username__isnull=True).exclude(username='').select_related('mikrotik_device')

    display_customers = []
    
    # Group by device for efficient querying
    device_customers = {}
    for c in past_due_customers:
        if c.mikrotik_device not in device_customers:
            device_customers[c.mikrotik_device] = []
        device_customers[c.mikrotik_device].append(c)
        
    for device, customers in device_customers.items():
        api = MikrotikAPI(device)
        secrets = api.get_ppp_secrets()
        
        # Build lookup dict
        secret_dict = {s.get('name'): s.get('profile', 'N/A') for s in secrets}
        
        for c in customers:
            profile = secret_dict.get(c.username, 'Not Found')
            if str(profile).lower() != 'expired':
                c.mikrotik_profile = profile
                display_customers.append(c)

    display_customers.sort(key=lambda x: x.full_name)
    
    context = {
        'due_customers': display_customers
    }
    return render(request, 'billing/auto_suspend.html', context)


@login_required
def statement_of_account_view(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    payments = customer.payments.all().order_by('-paid_at')
    
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
        'current_date': timezone.now()
    }
    return render(request, 'billing/statement_of_account.html', context)


@role_required(['Admin', 'Editor'])
@login_required
def bulk_transfer_router(request):
    """
    Handles bulk moving customers to a different Mikrotik router.
    """
    if request.method == 'POST':
        customer_ids = request.POST.getlist('customer_ids')
        target_device_id = request.POST.get('target_device_id')
        
        if not customer_ids or not target_device_id:
            messages.error(request, 'Please select customers and a target router.')
            return redirect('customer_list')
            
        try:
            from network_manager.models import MikrotikDevice
            target_device = MikrotikDevice.objects.get(id=target_device_id)
            
            transferred_count = 0
            for cid in customer_ids:
                customer = Customer.objects.get(id=cid)
                if str(customer.mikrotik_device_id) != str(target_device_id):
                    # Keep track of old device ID so the signal knows to delete the secret
                    customer._original_mikrotik_device_id = customer.mikrotik_device_id
                    
                    customer.mikrotik_device = target_device
                    customer.save() # Triggers post_save signal
                    transferred_count += 1
                    
            messages.success(request, f'Successfully transferred {transferred_count} customers to {target_device.device_name}.')
        except Exception as e:
            messages.error(request, f'Error during transfer: {str(e)}')
            
    return redirect('customer_list')


@require_POST
@role_required(['Admin', 'Editor'])
@login_required
def verify_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if not customer.is_verified:
        customer.is_verified = True
        customer.save(update_fields=['is_verified'])
        
        SystemLog.objects.create(
            table_name='Customer',
            record_id=str(customer.id),
            action='UPDATE',
            changed_by=request.user.username,
            target_name=customer.full_name,
            old_data='is_verified: False',
            new_data='is_verified: True (Admin Verified Rogue Account)'
        )
        
        messages.success(request, f'Account {customer.pppoe_username} has been verified and protected from auto-suspension.')
    else:
        messages.info(request, 'Account is already verified.')
        
    return redirect('view_customer', customer_id=customer.id)


@require_POST
@role_required(['Admin', 'Editor'])
@login_required
def unverify_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if customer.is_verified:
        customer.is_verified = False
        customer.save(update_fields=['is_verified'])
        
        SystemLog.objects.create(
            table_name='Customer',
            record_id=str(customer.id),
            action='UPDATE',
            changed_by=request.user.username,
            target_name=customer.full_name,
            old_data='is_verified: True',
            new_data='is_verified: False (Admin Unverified Account)'
        )
        
        messages.success(request, f'Account {customer.pppoe_username} has been unverified and is now subject to regular checks.')
    else:
        messages.info(request, 'Account is not verified.')
        
    return redirect('view_customer', customer_id=customer.id)
