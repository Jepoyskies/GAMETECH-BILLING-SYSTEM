from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count, Q
from billing.models import Customer, CignalPlay, AddOnRequest, Notification, Payment, AuditLog


@login_required
def cignal_dashboard_view(request):
    today = timezone.localtime().date()
    
    # KPIs
    active_customers = Customer.objects.filter(
        (Q(cignalplay_no__isnull=False) & ~Q(cignalplay_no__exact=""))
        | (Q(cignalbox_no__isnull=False) & ~Q(cignalbox_no__exact=""))
        | Q(cignal_plans__isnull=False)
    ).distinct()
    
    active_cignal_customers = active_customers.count()
    
    pending_applications = AddOnRequest.objects.filter(
        Q(addon_type__icontains='Cignal') | Q(addon_type__icontains='Box'),
        status='Pending'
    )
    pending_applications_count = pending_applications.count()
    
    new_cignal_this_month = CignalPlay.objects.filter(
        created_at__month=today.month, 
        created_at__year=today.year
    ).count()

    total_notifications = Notification.objects.filter(notification_type='cignal').count()

    # Expiring Soon Radar (Next 5 Days)
    in_5_days = today + timedelta(days=5)
    expiring_cignals = (
        CignalPlay.objects.filter(
            Q(expiration_date__date__gte=today, expiration_date__date__lte=in_5_days)
            | Q(end_date__date__gte=today, end_date__date__lte=in_5_days)
        )
        .select_related("customer")
        .order_by("expiration_date", "end_date")[:25]
    )

    # Tables Data
    # 1. Customers List with Prefetched Subscriptions
    customers_list = active_customers.prefetch_related('cignal_plans').order_by('-created_at')[:25]
    
    # 2. Cignal Logs/Renewals (Payments equivalent)
    cignal_payments = CignalPlay.objects.all().select_related('customer').order_by('-created_at')[:15]
    
    # 3. Notifications/Messages
    notifications = Notification.objects.filter(notification_type='cignal').order_by('-id')[:10]

    context = {
        'active_cignal_customers': active_cignal_customers,
        'pending_applications_count': pending_applications_count,
        'new_cignal_this_month': new_cignal_this_month,
        'total_notifications': total_notifications,
        'expiring_cignals': expiring_cignals,
        'customers_list': customers_list,
        'applications': pending_applications,
        'cignal_payments': cignal_payments,
        'notifications': notifications,
    }
    
    return render(request, "billing/cignal_dashboard.html", context)


@login_required
@require_POST
def process_cignal_payment(request):
    """
    Process manual payment / reload for a Cignal subscription (One-to-Many).
    Updates CignalPlay expiration date, logs payment in Payment table, and records AuditLog.
    """
    cignal_id = request.POST.get("cignal_id") or request.POST.get("subscription_id")
    customer_id = request.POST.get("customer_id")
    amount_raw = request.POST.get("amount") or request.POST.get("amount_paid") or "0"
    new_expiration_date_raw = request.POST.get("new_expiration_date") or request.POST.get("expiration_date")
    payment_method = request.POST.get("payment_method") or "Cash"
    reference_no = request.POST.get("reference_no", "").strip()
    notes = request.POST.get("notes", "").strip()

    try:
        amount = Decimal(str(amount_raw).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        amount = Decimal("0.00")

    with transaction.atomic():
        subscription = None
        if cignal_id and str(cignal_id).isdigit():
            subscription = CignalPlay.objects.select_for_update().filter(pk=cignal_id).first()

        if not subscription:
            if not customer_id:
                messages.error(request, "Please select a valid customer or subscription.")
                return redirect(request.META.get("HTTP_REFERER", "cignal_dashboard"))
            customer = get_object_or_404(Customer, pk=customer_id)
            subscription = CignalPlay.objects.select_for_update().filter(customer=customer).first()
            if not subscription:
                acct_num = customer.cignalplay_no or customer.cignalbox_no or "CIGNAL-001"
                is_box = bool(customer.cignalbox_no)
                subscription = CignalPlay.objects.create(
                    customer=customer,
                    plan_name="Cignal Box" if is_box else "Cignal Play",
                    addon_type="Cignal Box" if is_box else "Cignal Play",
                    account_name=f"{'Cignal Box' if is_box else 'Cignal Play'} - {acct_num}",
                    account_number=acct_num,
                    adjusted_by=request.user.username,
                )
        else:
            customer = subscription.customer

        new_expiration_date = None
        if new_expiration_date_raw:
            try:
                if len(new_expiration_date_raw) == 10:
                    dt = datetime.strptime(new_expiration_date_raw, "%Y-%m-%d")
                    new_expiration_date = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                else:
                    dt = datetime.fromisoformat(new_expiration_date_raw)
                    new_expiration_date = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
            except Exception:
                pass

        if new_expiration_date:
            subscription.expiration_date = new_expiration_date
            subscription.end_date = new_expiration_date

        subscription.amount_paid = (subscription.amount_paid or Decimal("0.00")) + amount
        subscription.adjusted_by = request.user.username
        subscription.save()

        # Build Reason text
        acct_desc = subscription.account_name or subscription.account_number or "Cignal Account"
        reason_text = f"Cignal Reload: {acct_desc}"
        if notes:
            reason_text += f" | {notes}"

        # Create Payment Record
        Payment.objects.create(
            customer=customer,
            username=customer.pppoe_username or customer.full_name,
            plan_name=f"{subscription.addon_type or 'Cignal'} ({subscription.plan_name})",
            amount=amount,
            payment_method=payment_method,
            reference_no=reference_no,
            reason=reason_text,
            expires_at=new_expiration_date or customer.expires_at,
            paid_at=timezone.now(),
            payment_date_received=timezone.now(),
            adjusted_by=request.user.username,
        )

        # Audit Log
        AuditLog.objects.create(
            customer=customer,
            action_type="Cignal Payment Reload",
            old_value=str(subscription.end_date or "None"),
            new_value=f"Amount: ₱{amount:,.2f} | Expiry: {new_expiration_date.strftime('%Y-%m-%d') if new_expiration_date else 'Unchanged'} | Acct: {subscription.account_number}",
            adjusted_by=request.user.username,
        )

        # Notification
        Notification.objects.create(
            title="Cignal Reload Recorded",
            message=f"₱{amount:,.2f} payment recorded for {customer.full_name} ({subscription.account_name or subscription.account_number}) by {request.user.username}.",
            notification_type="cignal",
            link=f"/customer/{customer.id}/cignal-logs/",
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
        return JsonResponse({
            "status": "success",
            "message": f"Payment of ₱{amount:,.2f} recorded successfully.",
            "subscription_id": subscription.id,
            "new_expiration": subscription.expiration_date.strftime("%Y-%m-%d") if subscription.expiration_date else "",
            "amount_paid": float(subscription.amount_paid),
        })

    messages.success(
        request,
        f"Cignal reload of ₱{amount:,.2f} successfully recorded for {customer.full_name} ({subscription.account_name or subscription.account_number}).",
    )
    return redirect(request.META.get("HTTP_REFERER", "cignal_dashboard"))

