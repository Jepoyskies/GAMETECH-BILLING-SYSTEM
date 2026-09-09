from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
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
    Customer, Barangay, Payment, Rebate, SystemLog, SmsLog, CignalPlay, AuditLog, AddOnRequest, Notification, ImprovementRequest, MessageTemplate
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar
from billing.views import calculate_new_expiration_date

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
            
            # Dynamic Status Update based on rollback time
            was_suspended = wrong_customer.status in ['suspended', 'inactive', 'expired']
            if wrong_customer.expires_at and wrong_customer.expires_at <= timezone.now() and wrong_customer.status == 'active':
                wrong_customer.status = 'expired'
            elif wrong_customer.expires_at and wrong_customer.expires_at > timezone.now() and was_suspended:
                wrong_customer.status = 'active'
                
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
                
                # Note: PPPoE comment generation is now handled automatically by billing/signals.py
                
                if was_suspended and new_customer.plan and new_customer.plan.name:
                    api_new.enable_pppoe_user(new_customer.pppoe_username)
                    api_new.kick_active_user(new_customer.pppoe_username)
            except Exception as e:
                pass # Non-critical

        messages.success(request, f"Payment successfully transferred from {wrong_customer.full_name} to {new_customer.full_name}.")
        return redirect(request.META.get('HTTP_REFERER', 'payment_logs'))
    return redirect('payment_logs')

