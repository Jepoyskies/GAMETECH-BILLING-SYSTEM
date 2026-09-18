from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
from decimal import Decimal
import json
import logging

from billing.models import Customer, Payment, SubscriptionPlan, Notification, AddOnRequest, SystemLog
from billing.views import calculate_new_expiration_date
from network_manager.services import MikrotikAPI

logger = logging.getLogger(__name__)


def portal_process_mock_payment(request):
    if request.method != "POST":
        return redirect("customer_portal:portal_dashboard")

    customer_id = request.session.get("customer_id")
    if not customer_id:
        return redirect("customer_portal:portal_login")

    amount = request.POST.get("amount")
    plan_id = request.POST.get("plan_id")
    payment_method = request.POST.get("payment_method", "Customer Portal (Mock)")

    if not amount:
        return redirect("customer_portal:portal_dashboard")

    try:
        amount_float = float(amount)
        customer = Customer.objects.get(id=customer_id)
        monthly_price = float(customer.plan.price) if customer.plan else 0.0

        if not customer.can_pay_staggered:
            if monthly_price > 0 and amount_float < monthly_price:
                messages.error(
                    request,
                    customer.staggered_restriction_reason
                    or f"Minimum payment allowed is 1 Month (P{monthly_price:.2f}). Staggered payments are not yet available for this account.",
                )
                return redirect("customer_portal:portal_dashboard")

        with transaction.atomic():
            locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)
            was_suspended = locked_customer.status in ["suspended", "inactive", "expired"]

            old_plan_name = locked_customer.plan.name if locked_customer.plan else "None"
            is_upgrade = False
            upgrade_fee = 0.0
            new_plan = None

            if plan_id and str(locked_customer.plan_id) != str(plan_id):
                new_plan = SubscriptionPlan.objects.get(id=plan_id)
                old_price = float(locked_customer.plan.price) if locked_customer.plan else 0.0
                monthly_price = float(new_plan.price)
                is_current_gimi = bool(locked_customer.plan and "GIMI" in locked_customer.plan.name)
                is_new_gimi = "GIMI" in new_plan.name
                if monthly_price < old_price:
                    raise Exception("Plan downgrades cannot be processed online. Please contact Gametech support.")
                if is_new_gimi and not is_current_gimi:
                    upgrade_fee = 500.0
                locked_customer.plan = new_plan
                if monthly_price > old_price or (is_new_gimi and not is_current_gimi):
                    is_upgrade = True

            current_exp = locked_customer.expires_at if (locked_customer.expires_at and locked_customer.expires_at > timezone.now()) else timezone.now()

            amount_for_time = max(0.0, amount_float - upgrade_fee)
            if locked_customer.outstanding_balance > 0:
                debt_paid = min(Decimal(str(amount_for_time)), locked_customer.outstanding_balance)
                locked_customer.outstanding_balance -= debt_paid
                amount_for_time = max(0.0, amount_for_time - float(debt_paid))

            if monthly_price > 0 and amount_for_time > monthly_price:
                used_for_time = monthly_price
                advance_excess = amount_for_time - monthly_price
                locked_customer.outstanding_balance -= Decimal(str(advance_excess))
            else:
                used_for_time = amount_for_time

            new_expiry = calculate_new_expiration_date(current_exp, used_for_time, monthly_price)
            locked_customer.expires_at = new_expiry
            if was_suspended:
                locked_customer.status = "active"
            locked_customer.save()

            reference = f"PORTAL-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            payment_reason = "Online Payment"
            if upgrade_fee > 0:
                payment_reason = f"Plan Upgrade to {locked_customer.plan.name} (includes P500 one-time upgrade fee)"

            Payment.objects.create(
                customer=locked_customer,
                username=locked_customer.pppoe_username,
                plan_name=locked_customer.plan.name if locked_customer.plan else None,
                amount=amount,
                payment_method=payment_method,
                reference_no=reference,
                reason=payment_reason,
                expires_at=new_expiry,
                adjusted_by="Customer Portal",
            )

            if upgrade_fee > 0:
                SystemLog.objects.create(
                    table_name="Customer",
                    record_id=str(locked_customer.id),
                    action="PLAN_UPGRADE",
                    changed_by="Customer Portal",
                    target_name=locked_customer.full_name,
                    old_data=f"Plan: {old_plan_name}",
                    new_data=f"Plan: {locked_customer.plan.name} | Upgrade Fee: P{upgrade_fee:.2f}",
                )

        if customer.mikrotik_device:
            try:
                api = MikrotikAPI(customer.mikrotik_device)
                expiry_str = new_expiry.strftime("%b %d, %Y")
                paid_str = timezone.now().strftime("%b %d, %Y")
                plan_name = customer.plan.name if customer.plan else "No Plan"
                comment_text = f"paid {paid_str} exp {expiry_str} . {plan_name} . {payment_method} . Customer Portal . Paid Online"
                api.set_pppoe_comment(customer.pppoe_username, comment_text)
            except Exception as e:
                logger.error(f"Failed to sync portal renewal for {customer.pppoe_username}: {e}")

        base_msg = f"Payment of P{amount} via {payment_method} successful! Your account is now active until {new_expiry.strftime('%b %d, %Y')}."
        if is_upgrade and new_plan:
            base_msg += f" Thank you for upgrading to {new_plan.name}! Enjoy your faster speeds."

        customer_url = reverse("view_customer", args=[customer.id])
        Notification.objects.create(
            title="Portal Payment Received",
            message=f"{customer.full_name} paid P{amount} via {payment_method}.",
            notification_type="payment",
            link=customer_url,
        )
        if is_upgrade and new_plan:
            Notification.objects.create(
                title="Plan Upgrade",
                message=f"{customer.full_name} upgraded their plan to {new_plan.name} via the portal.",
                notification_type="system",
                link=customer_url,
            )

        messages.success(request, base_msg)
    except Exception as e:
        messages.error(request, f"Payment processing failed: {e}")

    return redirect("customer_portal:portal_dashboard")


def portal_apply_addon(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

    customer_id = request.session.get("customer_id")
    if not customer_id:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
        addon_type = data.get("addon_type")
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid data"}, status=400)

    if not addon_type:
        return JsonResponse({"status": "error", "message": "Addon type is required"}, status=400)

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Customer not found"}, status=404)

    AddOnRequest.objects.create(customer=customer, addon_type=addon_type, status="Pending")
    customer_url = reverse("view_customer", args=[customer.id])
    Notification.objects.create(
        title=f"New Add-on Request: {addon_type}",
        message=f"{customer.full_name} has requested {addon_type}. Please contact them.",
        notification_type="cignal",
        link=customer_url,
    )
    return JsonResponse({"status": "success", "message": "Request submitted successfully. Our staff will contact you soon."})


@require_POST
def portal_cancel_addon(request, request_id):
    """
    Allow a customer to cancel their own pending add-on application if clicked accidentally.
    """
    customer_id = request.session.get("customer_id")
    if not customer_id:
        return JsonResponse({"status": "error", "message": "Unauthorized. Please log in."}, status=401)

    try:
        addon_req = AddOnRequest.objects.get(id=request_id, customer_id=customer_id, status="Pending")
    except AddOnRequest.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Pending request not found or already processed."}, status=404)

    addon_type = addon_req.addon_type
    addon_req.delete()

    return JsonResponse({
        "status": "success",
        "message": f"Your request for {addon_type} has been cancelled."
    })
