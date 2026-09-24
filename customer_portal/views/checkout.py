from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from decimal import Decimal

from billing.models import Customer, SubscriptionPlan

import logging
logger = logging.getLogger(__name__)


def portal_checkout(request):
    """
    Checkout page that sits between plan selection and the payment modal.
    Shows itemized line items (plan fee + optional GIMI upgrade fee),
    a voucher code placeholder, and an order summary with total.

    Query params:
        plan_id  — Optional. If provided and different from the customer's
                   current plan, shows the new plan as a line item with
                   upgrade fee if applicable.
    """
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('customer_portal:portal_login')
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect('customer_portal:portal_login')

    if customer.must_change_password:
        return redirect('customer_portal:force_change_password')

    # --- Determine which plan is being checked out ---
    selected_plan = customer.plan
    plan_id = request.GET.get('plan_id')
    is_upgrade = False
    upgrade_fee = Decimal('0.00')

    if plan_id:
        try:
            candidate = SubscriptionPlan.objects.get(id=plan_id)
            if customer.plan and candidate.pk != customer.plan.pk:
                old_price = customer.plan.price
                if candidate.price >= old_price:
                    selected_plan = candidate
                    is_upgrade = True
                    # GIMI upgrade fee: ₱500 one-time if upgrading TO a GIMI plan
                    is_current_gimi = bool(customer.plan and 'GIMI' in customer.plan.name)
                    is_new_gimi = 'GIMI' in candidate.name
                    if is_new_gimi and not is_current_gimi:
                        upgrade_fee = Decimal('500.00')
            elif not customer.plan:
                selected_plan = candidate
        except SubscriptionPlan.DoesNotExist:
            pass

    # --- Build line items ---
    line_items = []
    monthly_price = selected_plan.price if selected_plan else Decimal('0.00')

    if selected_plan:
        line_items.append({
            'name': selected_plan.name,
            'subtitle': f"{customer.full_name or customer.pppoe_username}'s Plan",
            'price': monthly_price,
            'icon': 'fa-solid fa-wifi',
            'icon_type': 'blue',
        })

    if upgrade_fee > 0:
        line_items.append({
            'name': 'GIMI Upgrade Fee',
            'subtitle': 'One-time charge',
            'price': upgrade_fee,
            'icon': 'fa-solid fa-bolt',
            'icon_type': 'orange',
        })

    total = monthly_price + upgrade_fee

    # --- Payment period options for the stack ---
    day_price = monthly_price / Decimal('30.0')
    payment_periods = [
        {'value': 3, 'label': '3 Days', 'price': (day_price * 3).quantize(Decimal('0.01')), 'selected': False, 'badge': '', 'badge_color': ''},
        {'value': 15, 'label': '15 Days', 'price': (day_price * 15).quantize(Decimal('0.01')), 'selected': False, 'badge': '', 'badge_color': ''},
        {'value': 30, 'label': '1 Month', 'price': monthly_price, 'selected': True, 'badge': 'MOST POPULAR', 'badge_color': 'gold'},
        {'value': 60, 'label': '2 Months', 'price': (monthly_price * 2).quantize(Decimal('0.01')), 'selected': False, 'badge': '', 'badge_color': ''},
        {'value': 90, 'label': '3 Months', 'price': (monthly_price * 3).quantize(Decimal('0.01')), 'selected': False, 'badge': 'SAVE 5%', 'badge_color': 'blue'},
        {'value': 180, 'label': '6 Months', 'price': (monthly_price * 6).quantize(Decimal('0.01')), 'selected': False, 'badge': '', 'badge_color': ''},
        {'value': 365, 'label': '1 Year', 'price': (monthly_price * 12).quantize(Decimal('0.01')), 'selected': False, 'badge': 'BEST VALUE', 'badge_color': 'gold'},
        {'value': 'custom', 'label': 'Custom', 'price': None, 'selected': False, 'badge': '', 'badge_color': ''},
    ]

    # --- Due date calculation ---
    current_due = customer.expires_at
    if not current_due:
        current_due = timezone.now()

    # --- Determine account suspension state (needed by the payment modal) ---
    is_account_suspended = customer.status in ['suspended', 'expired', 'inactive']

    # --- All available plans (needed by plan picker inside the payment modal) ---
    plans = SubscriptionPlan.objects.all().order_by('price')

    context = {
        'customer': customer,
        'plan': customer.plan,
        'selected_plan': selected_plan,
        'is_upgrade': is_upgrade,
        'upgrade_fee': upgrade_fee,
        'line_items': line_items,
        'total': total,
        'payment_periods': payment_periods,
        'current_due': current_due,
        'checkout_step': 2,
        'is_account_suspended': is_account_suspended,
        'plans': plans,
    }
    return render(request, 'customer_portal/portal_checkout.html', context)
