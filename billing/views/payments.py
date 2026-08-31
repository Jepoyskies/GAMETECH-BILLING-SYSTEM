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
def payment_logs_view(request):
    payments = Payment.objects.all().order_by('-paid_at')

    # Filtering
    filter_from = request.GET.get('from', '')
    filter_to = request.GET.get('to', '')
    filter_search = request.GET.get('search', '')
    filter_method = request.GET.get('method', '')

    if filter_from:
        payments = payments.filter(paid_at__gte=filter_from + ' 00:00:00')
    if filter_to:
        payments = payments.filter(paid_at__lte=filter_to + ' 23:59:59')
    if filter_search:
        payments = payments.filter(
            Q(username__icontains=filter_search)
            | Q(reference_no__icontains=filter_search)
        )
    if filter_method:
        payments = payments.filter(payment_method=filter_method)

    # Summaries
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    grand_total = Payment.objects.aggregate(t=Sum('amount'))['t'] or 0
    filtered_range_total = payments.aggregate(t=Sum('amount'))['t'] or 0

    total_today = payments.filter(
        paid_at__date=today).aggregate(t=Sum('amount'))['t'] or 0
    total_yesterday = payments.filter(
        paid_at__date=yesterday).aggregate(t=Sum('amount'))['t'] or 0

    # 14 days chart data
    chart_labels = []
    chart_values = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        chart_labels.append(d.strftime('%Y-%m-%d'))
        daily_total = payments.filter(
            paid_at__date=d).aggregate(t=Sum('amount'))['t'] or 0
        chart_values.append(float(daily_total))

    # Pagination
    per_page = int(request.GET.get('per_page', 35))
    paginator = Paginator(payments, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    methods = Payment.objects.exclude(payment_method__isnull=True).exclude(
        payment_method='').values_list('payment_method', flat=True).distinct().order_by('payment_method')

    context = {
        'page_obj': page_obj,
        'filter_from': filter_from,
        'filter_to': filter_to,
        'filter_search': filter_search,
        'filter_method': filter_method,
        'methods': methods,
        'all_customers': Customer.objects.all().order_by('full_name'),

        'grand_total': grand_total,
        'filtered_range_total': filtered_range_total,
        'total_today': total_today,
        'total_yesterday': total_yesterday,

        'chart_labels_js': json.dumps(chart_labels),
        'chart_values_js': json.dumps(chart_values),
    }
    
    q = request.GET.copy()
    if 'page' in q:
        del q['page']
    context['query_params'] = q.urlencode()

    return render(request, 'billing/payment_logs.html', context)


@login_required
def create_payment_view(request, customer_id):
    from django.shortcuts import get_object_or_404
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        reference_no = request.POST.get('reference_no')
        payment_date_received = request.POST.get('payment_date_received')
        reason = request.POST.get('reason')

        # Calculate days paid
        try:
            # Simple handling if provided in YYYY-MM-DDTHH:MM:SS format
            sd = datetime.fromisoformat(start_date.replace(
                'Z', '')) if start_date else timezone.now()
            ed = datetime.fromisoformat(end_date.replace(
                'Z', '')) if end_date else timezone.now()

            # ensure aware datetime
            if timezone.is_naive(sd):
                sd = timezone.make_aware(sd)
            if timezone.is_naive(ed):
                ed = timezone.make_aware(ed)

            days_paid = round((ed - sd).total_seconds() / (24 * 3600), 4)
        except Exception as e:
            print("Date parse err:", e)
            days_paid = 0
            ed = timezone.now()

        try:
            pdr = datetime.fromisoformat(
                payment_date_received.replace('Z', ''))
            if timezone.is_naive(pdr):
                pdr = timezone.make_aware(pdr)
        except Exception:
            pdr = timezone.now()

        Payment.objects.create(
            customer=customer,
            username=customer.pppoe_username or customer.full_name,
            plan_name=customer.plan.name if customer.plan else '',
            mikrotik_device_name=customer.mikrotik_device.device_name if customer.mikrotik_device else '',
            amount=amount,
            days_paid=days_paid,
            payment_method=payment_method,
            reference_no=reference_no,
            reason=reason,
            expires_at=ed,
            payment_date_received=pdr,
            paid_at=timezone.now(),
            adjusted_by=request.user.username if request.user.is_authenticated else 'system'
        )

        customer.expires_at = ed
        
        # If the customer was previously inactive or suspended, auto-reactivate them
        if customer.status in ['expired', 'suspended', 'inactive', 'past_due']:
            customer.status = 'active'
            
        customer.save()

        messages.success(
            request, f"Payment for {customer.pppoe_username or customer.full_name} processed successfully.")
        return redirect('payment_logs')

    return render(request, 'billing/pay.html', {'customer': customer})


@login_required
def rebates_logs_view(request):
    from ..models import Rebate
    rebates = Rebate.objects.all().order_by('-paid_at')

    search = request.GET.get('search', '').strip()
    if search:
        rebates = rebates.filter(
            Q(username__icontains=search) |
            Q(plan_name__icontains=search) |
            Q(adjusted_by__icontains=search) |
            Q(note__icontains=search)
        )

    context = {
        'rebates': rebates,
        'search': search,
    }
    return render(request, 'billing/rebates_logs.html', context)


@login_required
@permission_required('billing.add_rebate', raise_exception=True)
def customer_rebate_view(request, username):
    # Depending on how Antigravity named your field, it might be 'username' or 'pppoe_username'
    customer = get_object_or_404(Customer, pppoe_username=username) 

    if request.method == 'POST':
        new_expiry_str = request.POST.get('new_due_date_time')
        note = request.POST.get('note')
        
        if new_expiry_str:
            # Convert HTML datetime-local string to timezone-aware Python datetime
            new_expiry = timezone.datetime.fromisoformat(new_expiry_str)
            if timezone.is_naive(new_expiry):
                new_expiry = timezone.make_aware(new_expiry)

            old_expiry = customer.expires_at

            # 1. Update Customer Expiry
            customer.expires_at = new_expiry
            # customer.sms_sent_at = None  # TODO: Uncomment when SMS is added
            customer.save()

            # 2. Log the Rebate
            from ..models import Rebate
            Rebate.objects.create(
                customer=customer,
                username=customer.pppoe_username,
                plan_name=customer.plan.name if customer.plan else None,
                current_expiry=old_expiry,
                expires_at=new_expiry,
                note=note,
                adjusted_by=request.user.username
            )

            # 3. TODO: Sprint 4 - Call Mikrotik API to update PPPoE comment/disconnect
            
            # 4. Pass data to success page for copying
            context = {
                'customer': customer,
                'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S'),
                'adjusted_by': request.user.username,
                'action_type': 'Rebate',
                'amount': '0.00'
            }
            return render(request, 'billing/payment_success.html', context)

    context = {
        'customer': customer,
        'current_expiry_js': customer.expires_at.strftime('%Y-%m-%dT%H:%M:%S') if customer.expires_at else timezone.now().strftime('%Y-%m-%dT%H:%M:%S')
    }
    return render(request, 'billing/customer_rebate.html', context)


@login_required
@permission_required('billing.add_rollback', raise_exception=True)
def customer_rollback_view(request, username):
    customer = get_object_or_404(Customer, pppoe_username=username)

    if request.method == 'POST':
        rollback_to_str = request.POST.get('rollback_to')
        note = request.POST.get('note')
        
        if rollback_to_str:
            new_expiry = timezone.datetime.fromisoformat(rollback_to_str)
            if timezone.is_naive(new_expiry):
                new_expiry = timezone.make_aware(new_expiry)

            old_expiry = customer.expires_at

            # 1. Update Customer Expiry (Rollback)
            customer.expires_at = new_expiry
            customer.save()

            # 2. Log the Rollback
            from ..models import Rebate
            Rebate.objects.create(
                customer=customer,
                username=customer.pppoe_username,
                plan_name=customer.plan.name if customer.plan else None,
                current_expiry=old_expiry,
                expires_at=new_expiry,
                note=f"Rollback: {note}",
                adjusted_by=request.user.username
            )

            # 3. TODO: Sprint 4 - Mikrotik API Sync

            context = {
                'customer': customer,
                'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S'),
                'adjusted_by': request.user.username,
                'action_type': 'Rollback Expiry',
                'amount': '0.00'
            }
            return render(request, 'billing/payment_success.html', context)

    context = {
        'customer': customer,
        'current_expiry_js': customer.expires_at.strftime('%Y-%m-%dT%H:%M') if customer.expires_at else ''
    }
    return render(request, 'billing/customer_rollback.html', context)


@login_required
def payment_success_view(request):
    """Fallback view if someone accesses the URL directly"""
    return redirect('customer_list')


@login_required
def payment_addon_logs_view(request):
    """
    Replicates the legacy 'payment_addon_logs.php' view showing
    customers and their current plan status.
    """
    customers = Customer.objects.select_related('plan').all().order_by('-created_at')
    
    # Calculate simple stats
    now = timezone.now()
    active_count = customers.filter(expires_at__gte=now).count()
    expired_count = customers.filter(expires_at__lt=now).count()
    no_plan_count = customers.filter(plan__isnull=True).count()

    context = {
        'customers': customers,
        'active_count': active_count,
        'expired_count': expired_count,
        'no_plan_count': no_plan_count,
        'now': now,
    }
    return render(request, 'billing/payment_addon_logs.html', context)


@login_required
def payment_portal_view(request):
    """A centralized dashboard for cashiers to search and select a customer to pay."""
    customers = Customer.objects.select_related('plan').all().order_by('-created_at')
    return render(request, 'billing/payment_portal.html', {'customers': customers})


@login_required
@permission_required('billing.add_payment', raise_exception=True)
def pay_customer_view(request, username):
    customer = get_object_or_404(Customer, pppoe_username=username)
    
    # Calculate Monthly Price
    monthly_price = float(customer.plan.price) if customer.plan else 0.0

    # Capture dynamic redirect URL
    next_url = request.GET.get('next') or request.POST.get('next_url') or request.META.get('HTTP_REFERER') or reverse('payment_portal')

    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        reference_no = request.POST.get('reference_no', '')
        reason = request.POST.get('reason', '')
        new_plan_id = request.POST.get('new_plan_id')
        
        if amount:
            from decimal import Decimal
            amount_float = float(amount)
            
            # Determine baseline current expiration
            if start_date_str:
                current_exp = timezone.datetime.fromisoformat(start_date_str.replace('Z', ''))
                if timezone.is_naive(current_exp):
                    current_exp = timezone.make_aware(current_exp)
            elif customer.expires_at and customer.expires_at > timezone.now():
                current_exp = customer.expires_at
            else:
                current_exp = timezone.now()

            with transaction.atomic():
                # Lock the customer row for atomic update
                locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)
                
                # --- UPGRADE PLAN LOGIC ---
                is_upgrade = False
                is_downgrade = False
                old_plan_name = locked_customer.plan.name if locked_customer.plan else "None"
                
                if new_plan_id and str(locked_customer.plan_id) != str(new_plan_id):
                    new_plan = SubscriptionPlan.objects.filter(id=new_plan_id).first()
                    if new_plan:
                        old_price = float(locked_customer.plan.price) if locked_customer.plan else 0.0
                        monthly_price = float(new_plan.price)
                        locked_customer.plan = new_plan
                        if monthly_price > old_price:
                            is_upgrade = True
                        else:
                            is_downgrade = True
                        locked_customer.save() # Triggers Mikrotik Sync
                # --------------------------
                
                # --- Option B: Wallet/Advance Payment Logic ---
                amount_for_time = amount_float
                
                # Calculate new expiration using ONLY the amount meant for time
                new_expiry = calculate_new_expiration_date(current_exp, amount_for_time, monthly_price)

                was_suspended = locked_customer.status in ['suspended', 'inactive', 'expired']
                
                # 1. Update Customer Expiry
                locked_customer.expires_at = new_expiry
                
                # 2. Deduct from outstanding balance
                locked_customer.outstanding_balance -= Decimal(amount)
                
                # 3. Update Status if suspended
                if was_suspended:
                    locked_customer.status = 'active'
                
                locked_customer.save()

                # 4. Log the Payment
                payment = Payment.objects.create(
                    customer=locked_customer,
                    username=locked_customer.pppoe_username,
                    plan_name=locked_customer.plan.name if locked_customer.plan else None,
                    amount=amount, 
                    payment_method=payment_method, 
                    reference_no=reference_no, 
                    reason=reason, 
                    expires_at=new_expiry,
                    adjusted_by=request.user.username,
                    paid_at=timezone.now()
                )

                # Send Notification
                Notification.objects.create(
                    title=f"Payment Received: ₱{amount}",
                    message=f"{locked_customer.full_name} paid via {payment_method}.",
                    notification_type='payment',
                    link=f"/logs/payments/"
                )

            # 5. Mikrotik API Reactivation & Comments
            if customer.mikrotik_device:
                try:
                    from network_manager.services import MikrotikAPI
                    api = MikrotikAPI(customer.mikrotik_device)
                    
                    # Mikrotik Format: paid (date) exp (date) . plan . method . admin
                    expiry_str = new_expiry.strftime('%b %d, %Y')
                    paid_str = timezone.now().strftime('%b %d, %Y')
                    plan_name = customer.plan.name if customer.plan else "No Plan"
                    admin_name = request.user.username if request.user.is_authenticated else "Admin"
                    comment_text = f"paid {paid_str} exp {expiry_str} . {plan_name} . {payment_method} . {admin_name} . {reason}"
                    api.set_pppoe_comment(customer.pppoe_username, comment_text)
                    
                    if was_suspended:
                        # 1. Enable the user (Removes bridge drop and enables secret)
                        api.enable_pppoe_user(customer.pppoe_username)
                        # 2. Update the profile back to their plan, or default if none
                        target_profile = customer.plan.name if customer.plan and customer.plan.name else "default"
                        api.set_user_pppoe_profile(customer.pppoe_username, target_profile)
                        # 3. Kick them so they reconnect and get the new profile
                        api.kick_active_user(customer.pppoe_username)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to sync renewal for {customer.pppoe_username} on MikroTik: {e}")

            # 4. Success Output
            
            # Generate Messenger Template
            messenger_msg = f"Hi {customer.full_name},\n\nThank you for your payment of ₱{amount} via {payment_method}. Your internet connection is now active until {new_expiry.strftime('%B %d, %Y')}."
            if is_upgrade:
                messenger_msg += f"\n\nThank you for upgrading to {new_plan.name}! Enjoy your faster speeds."
            elif is_downgrade:
                messenger_msg += f"\n\nYour plan has been successfully updated to {new_plan.name}. If you wish to upgrade soon for faster speeds, you can always let us know!"
            
            context = {
                'customer': customer,
                'new_expiry': new_expiry.strftime('%Y-%m-%d %H:%M:%S'),
                'adjusted_by': request.user.username,
                'action_type': 'Standard Renewal',
                'amount': amount,
                'next_url': next_url,
                'messenger_template': messenger_msg,
            }
            return render(request, 'billing/payment_success.html', context)

    # GET Request: Setup defaults
    current_expiry = customer.expires_at or timezone.now()
    start_default_str = current_expiry.strftime('%Y-%m-%dT%H:%M:%S')
    
    # Add roughly one month for the default end date
    end_default = current_expiry + timezone.timedelta(days=30)
    end_default_str = end_default.strftime('%Y-%m-%dT%H:%M:%S')

    plans = SubscriptionPlan.objects.all().order_by('price')

    context = {
        'customer': customer,
        'plans': plans,
        'current_expiry_display': current_expiry.strftime('%Y-%m-%d %H:%M:%S'),
        'start_default_str': start_default_str,
        'end_default_str': end_default_str,
        'monthly_price': monthly_price,
        'next_url': next_url,
    }
    return render(request, 'billing/pay_customer.html', context)


@role_required(['Admin'])
@login_required
def edit_payment_log_view(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    
    if request.method == 'POST':
        old_method = payment.payment_method
        old_amount = payment.amount
        old_ref = payment.reference_no
        old_reason = payment.reason

        new_method = request.POST.get('payment_method')
        new_amount = request.POST.get('amount')
        new_ref = request.POST.get('reference_no', '')
        new_reason = request.POST.get('reason', '')

        # Construct audit log remarks
        changes = []
        if str(old_method) != str(new_method):
            changes.append(f"Method: {old_method} -> {new_method}")
        if str(old_amount) != str(new_amount):
            changes.append(f"Amount: {old_amount} -> {new_amount}")
        if str(old_ref) != str(new_ref):
            changes.append(f"Reference: {old_ref} -> {new_ref}")
        if str(old_reason) != str(new_reason):
            changes.append(f"Reason: {old_reason} -> {new_reason}")

        if changes:
            payment.payment_method = new_method
            if new_amount:
                payment.amount = new_amount
            payment.reference_no = new_ref
            payment.reason = new_reason
            payment.save()

            AuditLog.objects.create(
                admin_user=request.user,
                customer=payment.customer,
                action_type='Edit Payment Log',
                remarks=f"Edited Payment #{payment.id}. Changes: {', '.join(changes)}"
            )
            messages.success(request, f"Payment #{payment.id} successfully updated.")
        
        return redirect('payment_logs')

    context = {
        'payment': payment
    }
    return render(request, 'billing/edit_payment_log.html', context)


@login_required
@role_required(['Admin'])
def revert_transfer_payment(request, payment_id):
    if request.method == 'POST':
        payment = get_object_or_404(Payment, id=payment_id)
        wrong_customer = payment.customer
        new_customer_id = request.POST.get('new_customer_id')
        
        if not new_customer_id:
            messages.error(request, "You must select a new customer to transfer the payment to.")
            return redirect(request.META.get('HTTP_REFERER', 'payment_logs'))
            
        new_customer = get_object_or_404(Customer, id=new_customer_id)
        
        if wrong_customer.id == new_customer.id:
            messages.error(request, "Cannot transfer payment to the same customer.")
            return redirect(request.META.get('HTTP_REFERER', 'payment_logs'))

        with transaction.atomic():
            # Lock both customers
            wrong_customer = Customer.objects.select_for_update().get(pk=wrong_customer.pk)
            new_customer = Customer.objects.select_for_update().get(pk=new_customer.pk)
            
            # --- Revert Wrong Customer ---
            monthly_price = float(wrong_customer.plan.price) if wrong_customer.plan else 0.0
            if monthly_price > 0:
                days_to_subtract = float(payment.amount) / (monthly_price / 30)
                from datetime import timedelta
                if wrong_customer.expires_at:
                    wrong_customer.expires_at = wrong_customer.expires_at - timedelta(days=days_to_subtract)
            
            wrong_customer.outstanding_balance += payment.amount
            wrong_customer.save()
            
            # --- Apply to New Customer ---
            monthly_price_new = float(new_customer.plan.price) if new_customer.plan else 0.0
            current_exp = new_customer.expires_at if (new_customer.expires_at and new_customer.expires_at > timezone.now()) else timezone.now()
            new_expiry = calculate_new_expiration_date(current_exp, float(payment.amount), monthly_price_new)
            
            was_suspended = new_customer.status in ['suspended', 'inactive', 'expired']
            new_customer.expires_at = new_expiry
            new_customer.outstanding_balance -= payment.amount
            if was_suspended:
                new_customer.status = 'active'
            new_customer.save()
            
            # Transfer the payment record
            payment.customer = new_customer
            payment.username = new_customer.pppoe_username
            payment.plan_name = new_customer.plan.name if new_customer.plan else None
            payment.expires_at = new_expiry
            payment.reason = f"[TRANSFERRED FROM {wrong_customer.full_name}] " + (payment.reason or "")
            payment.save()
            
            from ..models import SystemLog
            SystemLog.objects.create(
                table_name='Payment',
                record_id=str(payment.id),
                action='UPDATE',
                changed_by=request.user.username,
                target_name=new_customer.full_name,
                old_data=f"Belonged to {wrong_customer.full_name}",
                new_data=f"Transferred to {new_customer.full_name}"
            )

        # --- Mikrotik Logic (Outside Atomic to prevent DB locks during network calls) ---
        from network_manager.services import MikrotikAPI
        # Kick wrong customer so router redials and suspends if due
        if wrong_customer.mikrotik_device:
            try:
                api_wrong = MikrotikAPI(wrong_customer.mikrotik_device)
                api_wrong.kick_active_user(wrong_customer.pppoe_username)
            except Exception as e:
                pass # Non-critical
                
        # Reactivate new customer
        if new_customer.mikrotik_device:
            try:
                api_new = MikrotikAPI(new_customer.mikrotik_device)
                
                expiry_str = new_expiry.strftime('%b %d, %Y')
                paid_str = payment.created_at.strftime('%b %d, %Y')
                plan_name = new_customer.plan.name if new_customer.plan else "No Plan"
                comment_text = f"paid {paid_str} exp {expiry_str} . {plan_name} . {payment.payment_method} . Transfer"
                api_new.set_pppoe_comment(new_customer.pppoe_username, comment_text)
                
                if was_suspended and new_customer.plan and new_customer.plan.name:
                    api_new.enable_pppoe_user(new_customer.pppoe_username)
                    api_new.kick_active_user(new_customer.pppoe_username)
            except Exception as e:
                pass # Non-critical

        messages.success(request, f"Payment successfully transferred from {wrong_customer.full_name} to {new_customer.full_name}.")
        return redirect(request.META.get('HTTP_REFERER', 'payment_logs'))
    return redirect('payment_logs')


