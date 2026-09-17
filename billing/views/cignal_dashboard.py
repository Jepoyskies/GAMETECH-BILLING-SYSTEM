from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count, Q, Prefetch
from billing.models import Customer, CignalPlay, AddOnRequest, Notification, Payment, AuditLog


@login_required
def cignal_dashboard_view(request):
    today = timezone.localtime().date()
    current_tab = request.GET.get("tab", "active")

    # KPIs: only customers with non-cancelled Cignal plans count as active
    active_cignal_customers = Customer.objects.filter(
        cignal_plans__is_cancelled=False
    ).distinct().count()

    pending_applications = AddOnRequest.objects.filter(
        Q(addon_type__icontains="Cignal") | Q(addon_type__icontains="Box"),
        status="Pending",
    )
    pending_applications_count = pending_applications.count()

    new_cignal_this_month = CignalPlay.objects.filter(
        is_cancelled=False,
        created_at__month=today.month,
        created_at__year=today.year,
    ).count()

    total_notifications = Notification.objects.filter(notification_type="cignal").count()

    # Expiring Soon Radar (Next 5 Days) - Active only
    in_5_days = today + timedelta(days=5)
    expiring_cignals = (
        CignalPlay.objects.filter(is_cancelled=False)
        .filter(
            Q(expiration_date__date__gte=today, expiration_date__date__lte=in_5_days)
            | Q(end_date__date__gte=today, end_date__date__lte=in_5_days)
        )
        .select_related("customer")
        .order_by("expiration_date", "end_date")[:25]
    )

    # Status counts for navigation bar
    count_active = active_cignal_customers
    count_installment = Customer.objects.filter(
        cignal_plans__is_cancelled=False,
        cignal_plans__hardware_payment_type="installment",
        cignal_plans__installments_paid__lt=12,
    ).distinct().count()
    count_fully_paid = Customer.objects.filter(
        cignal_plans__is_cancelled=False
    ).filter(
        Q(cignal_plans__hardware_payment_type="cashout")
        | (Q(cignal_plans__hardware_payment_type="installment") & Q(cignal_plans__installments_paid__gte=12))
    ).distinct().count()
    count_deleted = CignalPlay.objects.filter(is_cancelled=True).count()

    # Segmented table dataset
    cancelled_plans = None
    if current_tab == "installment":
        customers_list = (
            Customer.objects.filter(
                cignal_plans__is_cancelled=False,
                cignal_plans__hardware_payment_type="installment",
                cignal_plans__installments_paid__lt=12,
            )
            .distinct()
            .prefetch_related(
                Prefetch(
                    "cignal_plans",
                    queryset=CignalPlay.objects.filter(
                        is_cancelled=False,
                        hardware_payment_type="installment",
                        installments_paid__lt=12,
                    ),
                )
            )
            .order_by("-created_at")[:50]
        )
    elif current_tab == "fully_paid":
        customers_list = (
            Customer.objects.filter(cignal_plans__is_cancelled=False)
            .filter(
                Q(cignal_plans__hardware_payment_type="cashout")
                | (Q(cignal_plans__hardware_payment_type="installment") & Q(cignal_plans__installments_paid__gte=12))
            )
            .distinct()
            .prefetch_related(
                Prefetch("cignal_plans", queryset=CignalPlay.objects.filter(is_cancelled=False))
            )
            .order_by("-created_at")[:50]
        )
    elif current_tab == "deleted":
        customers_list = []
        cancelled_plans = (
            CignalPlay.objects.filter(is_cancelled=True)
            .select_related("customer")
            .order_by("-cancelled_at")[:50]
        )
    elif current_tab == "expiring_soon":
        customers_list = []
    else:
        current_tab = "active"
        customers_list = (
            Customer.objects.filter(cignal_plans__is_cancelled=False)
            .distinct()
            .prefetch_related(
                Prefetch("cignal_plans", queryset=CignalPlay.objects.filter(is_cancelled=False))
            )
            .order_by("-created_at")[:50]
        )

    # 2. Cignal Logs/Renewals (Payments equivalent)
    cignal_payments = CignalPlay.objects.all().select_related("customer").order_by("-created_at")[:15]

    # 3. Notifications/Messages (5 items max for sleek right sidebar)
    notifications = Notification.objects.filter(notification_type="cignal").order_by("-id")[:5]

    # 4. All Customers for Enrollment Selector
    all_customers = Customer.objects.all().order_by("full_name", "pppoe_username")
    default_cignal_due_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")

    context = {
        "current_tab": current_tab,
        "active_cignal_customers": active_cignal_customers,
        "pending_applications_count": pending_applications_count,
        "new_cignal_this_month": new_cignal_this_month,
        "total_notifications": total_notifications,
        "expiring_cignals": expiring_cignals,
        "customers_list": customers_list,
        "cancelled_plans": cancelled_plans,
        "count_active": count_active,
        "count_installment": count_installment,
        "count_fully_paid": count_fully_paid,
        "count_deleted": count_deleted,
        "applications": pending_applications,
        "cignal_payments": cignal_payments,
        "notifications": notifications,
        "all_customers": all_customers,
        "default_cignal_due_date": default_cignal_due_date,
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
    payment_type = request.POST.get("payment_type", "").strip()

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
                acct_parts = []
                if customer.cignalplay_no:
                    acct_parts.append(f"Play: {customer.cignalplay_no}")
                if customer.cignalbox_no:
                    acct_parts.append(f"Box: {customer.cignalbox_no}")
                acct_str = " | ".join(acct_parts) if acct_parts else "CIGNAL-001"
                subscription = CignalPlay.objects.create(
                    customer=customer,
                    plan_name="Cignal Subscription",
                    account_name=f"Cignal - {acct_str}",
                    cignal_play_no=customer.cignalplay_no or "",
                    cignal_box_no=customer.cignalbox_no or "",
                    adjusted_by=request.user.username,
                )
        else:
            customer = subscription.customer

        new_expiration_date = None
        if new_expiration_date_raw:
            try:
                if len(new_expiration_date_raw) == 10:
                    dt = datetime.strptime(new_expiration_date_raw, "%Y-%m-%d")
                    dt = dt.replace(hour=23, minute=59, second=59)
                    new_expiration_date = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                else:
                    dt = datetime.fromisoformat(new_expiration_date_raw)
                    new_expiration_date = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
            except Exception:
                pass

        # ISP-style automatic date advancement if not manually specified:
        # Load payments advance by 30 days from current expiry (if active) or from today (if expired)
        if not new_expiration_date and payment_type not in ("box_only", "box_installment"):
            curr_exp = subscription.expiration_date or subscription.end_date
            if curr_exp and curr_exp > timezone.now():
                base_dt = curr_exp
            else:
                base_dt = timezone.now()
            new_expiration_date = (base_dt + timedelta(days=30)).replace(hour=23, minute=59, second=59)

        if new_expiration_date and payment_type not in ("box_only", "box_installment"):
            subscription.expiration_date = new_expiration_date
            subscription.end_date = new_expiration_date

        # Process hardware installment or cashout increments
        installment_text = ""
        if payment_type == "box_and_load" or (payment_type != "load_only" and amount == Decimal("399.00") and subscription.hardware_payment_type == "installment" and (subscription.installments_paid or 0) < 12 and subscription.monthly_load_plan == "149"):
            if subscription.hardware_payment_type == "installment" and (subscription.installments_paid or 0) < 12:
                subscription.installments_paid = (subscription.installments_paid or 0) + 1
                installment_text = f" [Box Installment #{subscription.installments_paid}/12 (₱250) + Load (₱149)]"
            else:
                installment_text = " [Box + Load: ₱399]"
        elif payment_type in ("box_installment", "box_only") or (payment_type != "load_only" and amount == Decimal("250.00") and subscription.hardware_payment_type == "installment" and (subscription.installments_paid or 0) < 12):
            if subscription.hardware_payment_type == "installment" and (subscription.installments_paid or 0) < 12:
                subscription.installments_paid = (subscription.installments_paid or 0) + 1
                installment_text = f" [Box Installment #{subscription.installments_paid}/12 (₱250)]"
            else:
                installment_text = " [Box Installment: ₱250]"
        elif payment_type == "box_cashout" or amount >= Decimal("3000.00"):
            subscription.hardware_payment_type = "cashout"
            subscription.installments_paid = 12
            installment_text = " [Hardware Cashout ₱3k Completed]"

        subscription.amount_paid = (subscription.amount_paid or Decimal("0.00")) + amount
        subscription.adjusted_by = request.user.username
        subscription.save()

        # Build Reason text
        acct_desc = subscription.account_name or subscription.account_number or "Cignal Account"
        reason_text = f"Cignal Reload: {acct_desc}{installment_text}"
        if notes:
            reason_text += f" | {notes}"

        # Create Payment Record
        Payment.objects.create(
            customer=customer,
            username=customer.pppoe_username or customer.full_name,
            plan_name="Cignal Subscription",
            amount=amount,
            payment_method=payment_method,
            reference_no=reference_no,
            reason=reason_text,
            expires_at=subscription.expiration_date or customer.expires_at,
            paid_at=timezone.now(),
            payment_date_received=timezone.now(),
            adjusted_by=request.user.username,
        )

        # Audit Log
        audit_notes = f" | Notes: {notes}" if notes else ""
        AuditLog.objects.create(
            admin_user=request.user,
            customer=customer,
            action_type="Cignal Payment Reload",
            remarks=f"Amount: ₱{amount:,.2f} | Type: {payment_type or 'load'} | HW: {subscription.hardware_payment_type} ({subscription.installments_paid}/12) | Ref: {reference_no or 'N/A'}{audit_notes} | Expiry: {new_expiration_date.strftime('%Y-%m-%d') if new_expiration_date else 'Unchanged'} | Acct: {subscription.account_number}",
        )

        # Notification
        Notification.objects.create(
            title="Cignal Reload Recorded",
            message=f"₱{amount:,.2f} payment recorded for {customer.full_name} ({subscription.account_name or subscription.account_number}) by {request.user.username}.{installment_text}",
            notification_type="cignal",
            link=f"/customer/{customer.id}/cignal-logs/",
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
        return JsonResponse({
            "status": "success",
            "message": f"Payment of ₱{amount:,.2f} recorded successfully.{installment_text}",
            "subscription_id": subscription.id,
            "new_expiration": subscription.expiration_date.strftime("%Y-%m-%d") if subscription.expiration_date else "",
            "amount_paid": float(subscription.amount_paid),
            "installments_paid": subscription.installments_paid,
            "hardware_payment_type": subscription.hardware_payment_type,
        })

    inst_msg = f" (Box Installment #{subscription.installments_paid}/12)" if subscription.hardware_payment_type == 'installment' else ""
    messages.success(
        request,
        f"Cignal reload of ₱{amount:,.2f} successfully recorded for {customer.full_name} ({subscription.account_name or subscription.account_number}){inst_msg}.",
    )
    return redirect(request.META.get("HTTP_REFERER", "cignal_dashboard"))


@login_required
@require_POST
def edit_cignal_subscription(request, sub_id=None):
    """
    Update Cignal subscription details: label/account_name, cignal_play_no, cignal_box_no, hardware, and plan.
    Supports sub_id=None or 0 via customer_id fallback for customers without pre-existing CignalPlay records.
    """
    subscription = None
    if sub_id and int(sub_id) > 0:
        subscription = get_object_or_404(CignalPlay, pk=sub_id)
        customer = subscription.customer
    else:
        customer_id = request.POST.get("customer_id")
        if not customer_id:
            messages.error(request, "A valid subscription or customer identifier is required.")
            return redirect(request.META.get("HTTP_REFERER", "cignal_dashboard"))
        customer = get_object_or_404(Customer, pk=customer_id)
        subscription = CignalPlay.objects.filter(customer=customer).first()
        if not subscription:
            acct_parts = []
            if customer.cignalplay_no:
                acct_parts.append(f"Play: {customer.cignalplay_no}")
            if customer.cignalbox_no:
                acct_parts.append(f"Box: {customer.cignalbox_no}")
            acct_str = " | ".join(acct_parts) if acct_parts else "CIGNAL-001"
            subscription = CignalPlay.objects.create(
                customer=customer,
                plan_name="Cignal Subscription",
                account_name=f"Cignal - {acct_str}",
                cignal_play_no=customer.cignalplay_no or "",
                cignal_box_no=customer.cignalbox_no or "",
                adjusted_by=request.user.username,
            )

    account_name = request.POST.get("account_name", "").strip()
    cignal_play_no = request.POST.get("cignal_play_no", "").strip()
    cignal_box_no = request.POST.get("cignal_box_no", "").strip()
    hardware_payment_type = request.POST.get("hardware_payment_type", "").strip()
    installments_paid_raw = request.POST.get("installments_paid")
    monthly_load_plan = request.POST.get("monthly_load_plan", "").strip()

    if account_name:
        subscription.account_name = account_name
    subscription.cignal_play_no = cignal_play_no
    subscription.cignal_box_no = cignal_box_no

    if hardware_payment_type in ("cashout", "installment", "none"):
        subscription.hardware_payment_type = hardware_payment_type
        if hardware_payment_type == "cashout":
            subscription.installments_paid = 12

    if installments_paid_raw is not None and str(installments_paid_raw).strip().isdigit():
        subscription.installments_paid = min(12, max(0, int(installments_paid_raw)))

    if monthly_load_plan in ("149", "399"):
        subscription.monthly_load_plan = monthly_load_plan

    # Expiration / Due Date handling
    expiration_date_raw = request.POST.get("expiration_date", "").strip()
    if expiration_date_raw:
        try:
            exp_dt = None
            if "T" in expiration_date_raw:
                clean_dt = expiration_date_raw.replace("Z", "")
                exp_dt = datetime.fromisoformat(clean_dt)
            elif " " in expiration_date_raw:
                exp_dt = datetime.strptime(expiration_date_raw, "%Y-%m-%d %H:%M:%S")
            else:
                exp_dt = datetime.strptime(expiration_date_raw, "%Y-%m-%d")
                exp_dt = exp_dt.replace(hour=23, minute=59, second=59)

            if timezone.is_naive(exp_dt):
                exp_dt = timezone.make_aware(exp_dt, timezone.get_current_timezone())
            subscription.expiration_date = exp_dt
            subscription.end_date = exp_dt
        except Exception:
            pass
    elif "expiration_date" in request.POST and not expiration_date_raw:
        subscription.expiration_date = None
        subscription.end_date = None

    subscription.adjusted_by = request.user.username
    subscription.save()

    # Synchronize customer-level convenience fields if applicable
    if customer:
        updated_cust = False
        if cignal_play_no and customer.cignalplay_no != cignal_play_no:
            customer.cignalplay_no = cignal_play_no
            updated_cust = True
        if cignal_box_no and customer.cignalbox_no != cignal_box_no:
            customer.cignalbox_no = cignal_box_no
            updated_cust = True
        if updated_cust:
            customer.save(update_fields=["cignalplay_no", "cignalbox_no"])

    # AuditLog
    exp_str = subscription.expiration_date.strftime('%Y-%m-%d %H:%M') if subscription.expiration_date else 'None'
    AuditLog.objects.create(
        admin_user=request.user,
        customer=customer,
        action_type="Edit Cignal Subscription",
        remarks=f"Updated Cignal #{subscription.id}: Label='{subscription.account_name}', Play='{cignal_play_no}', Box='{cignal_box_no}', HW='{subscription.hardware_payment_type}' ({subscription.installments_paid}/12), Load='₱{subscription.monthly_load_plan}', Expiry='{exp_str}'",
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
        return JsonResponse({
            "status": "success",
            "message": "Cignal subscription updated successfully.",
            "subscription_id": subscription.id,
            "account_name": subscription.account_name,
            "cignal_play_no": subscription.cignal_play_no,
            "cignal_box_no": subscription.cignal_box_no,
            "hardware_payment_type": subscription.hardware_payment_type,
            "installments_paid": subscription.installments_paid,
            "monthly_load_plan": subscription.monthly_load_plan,
            "expiration_date": subscription.expiration_date.strftime("%Y-%m-%dT%H:%M") if subscription.expiration_date else "",
        })

    cust_name = customer.full_name if customer else "Customer"
    label_text = f" ({subscription.account_name})" if subscription.account_name and subscription.account_name.strip() not in ("Cignal Subscription", "Cignal Account") else ""
    messages.success(request, f"Cignal details for {cust_name}{label_text} updated successfully.")
    return redirect(request.META.get("HTTP_REFERER", "cignal_dashboard"))


@login_required
@require_POST
def cancel_cignal_subscription(request, sub_id):
    """Soft-cancel (pull-out) a Cignal subscription. Moves to Cancelled / Deleted Bar."""
    from dispatch.models import JobTicket

    subscription = get_object_or_404(CignalPlay, id=sub_id)
    customer = subscription.customer
    sub_label = subscription.account_name or f"Cignal #{subscription.id}"

    # Cancel any open dispatch ticket linked to this customer for Cignal
    JobTicket.objects.filter(
        customer=customer,
        ticket_type='CIGNAL',
        status__in=['PENDING', 'ASSIGNED'],
    ).update(status='CANCELLED')

    subscription.is_cancelled = True
    subscription.cancelled_at = timezone.now()
    subscription.cancelled_by = request.user.username
    subscription.save(update_fields=['is_cancelled', 'cancelled_at', 'cancelled_by'])

    # Clean legacy customer fields if no active plans remain
    remaining = customer.cignal_plans.filter(is_cancelled=False)
    if not remaining.exists():
        customer.cignalplay_no = None
        customer.cignalbox_no = None
        customer.save(update_fields=['cignalplay_no', 'cignalbox_no'])

    AuditLog.objects.create(
        admin_user=request.user,
        customer=customer,
        action_type="Cignal Cancellation",
        remarks=f"Cancelled Cignal subscription '{sub_label}' (ID #{subscription.id}) | Play: {subscription.cignal_play_no or 'N/A'} | Box: {subscription.cignal_box_no or 'N/A'} | by {request.user.username}. Moved to Cancelled Bar.",
    )

    Notification.objects.create(
        title="Cignal Subscription Cancelled",
        message=f"{customer.full_name}'s Cignal subscription '{sub_label}' was moved to the Cancelled Bar by {request.user.username}.",
        notification_type="cignal",
        link="/cignal-dashboard/?tab=deleted",
    )

    messages.success(request, f"Cignal subscription '{sub_label}' for {customer.full_name} moved to Cancelled / Deleted Bar.")
    return redirect("/cignal-dashboard/?tab=deleted")


@login_required
@require_POST
def restore_cignal_subscription(request, sub_id):
    """Restore a cancelled Cignal subscription back to active."""
    subscription = get_object_or_404(CignalPlay, id=sub_id, is_cancelled=True)
    customer = subscription.customer
    sub_label = subscription.account_name or f"Cignal #{subscription.id}"

    subscription.is_cancelled = False
    subscription.cancelled_at = None
    subscription.cancelled_by = None
    subscription.save(update_fields=['is_cancelled', 'cancelled_at', 'cancelled_by'])

    if subscription.cignal_play_no and not customer.cignalplay_no:
        customer.cignalplay_no = subscription.cignal_play_no
        customer.save(update_fields=['cignalplay_no'])
    if subscription.cignal_box_no and not customer.cignalbox_no:
        customer.cignalbox_no = subscription.cignal_box_no
        customer.save(update_fields=['cignalbox_no'])

    AuditLog.objects.create(
        admin_user=request.user,
        customer=customer,
        action_type="Cignal Restored",
        remarks=f"Restored Cignal subscription '{sub_label}' (ID #{subscription.id}) by {request.user.username}",
    )
    messages.success(request, f"Cignal subscription '{sub_label}' for {customer.full_name} has been restored.")
    return redirect("/cignal-dashboard/?tab=active")


@login_required
@require_POST
def purge_cignal_subscription(request, sub_id):
    """Permanently delete a cancelled subscription (Admin only)."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: Only administrators can permanently clear cancelled subscriptions.")
        return redirect("/cignal-dashboard/?tab=deleted")

    subscription = get_object_or_404(CignalPlay, id=sub_id, is_cancelled=True)
    customer = subscription.customer
    sub_label = subscription.account_name or f"Cignal #{subscription.id}"

    AuditLog.objects.create(
        admin_user=request.user,
        customer=customer,
        action_type="Cignal Permanent Purge",
        remarks=f"Permanently purged cancelled subscription '{sub_label}' (ID #{subscription.id}) by admin {request.user.username}",
    )
    subscription.delete()
    messages.success(request, f"Cancelled subscription '{sub_label}' has been permanently purged.")
    return redirect("/cignal-dashboard/?tab=deleted")


@login_required
@require_POST
def purge_all_cancelled_cignal_subscriptions(request):
    """Permanently clear all items in the cancelled / deleted bar (Admin only)."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: Only administrators can clear the archive bar.")
        return redirect("/cignal-dashboard/?tab=deleted")

    count, _ = CignalPlay.objects.filter(is_cancelled=True).delete()
    # Also clean orphaned legacy numbers on any customer with 0 plans
    for c in Customer.objects.filter(cignal_plans__isnull=True):
        if c.cignalplay_no or c.cignalbox_no:
            c.cignalplay_no = None
            c.cignalbox_no = None
            c.save(update_fields=['cignalplay_no', 'cignalbox_no'])

    AuditLog.objects.create(
        admin_user=request.user,
        customer=None,
        action_type="Cignal Archive Cleared",
        remarks=f"Admin {request.user.username} cleared all {count} cancelled subscriptions from archive bar.",
    )
    messages.success(request, f"Successfully purged {count} item(s) from the cancelled bar.")
    return redirect("/cignal-dashboard/?tab=deleted")



