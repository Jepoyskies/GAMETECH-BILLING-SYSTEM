"""
Nightly expiry sweep -- BILLING ONLY, NEVER TOUCHES A ROUTER.

Why this exists
---------------
`auto_suspend` is deliberately NOT scheduled (project rule: nothing writes to a
router unattended). But that leaves a hole the owner cares about most: after a
cutover, a subscriber whose expiry has passed keeps `status='active'` forever,
because nothing runs overnight. Staff only find out by opening the customer
list.

So this task does the safe half:
  * counts who is past due, split by whether they are still online
  * raises ONE Notification for staff so the bell tells them
  * auto-renews from advance payment where the customer already paid ahead
  * NEVER calls the router. Suspending stays a deliberate human action via the
    "Connected, Unpaid" queue, exactly as the lifecycle vocabulary intends.

Billing truth changes; hardware is untouched. That is Rule 35.
"""
from django.db.models import Q
from django.utils import timezone

from billing.decorators import billing_required  # noqa: F401  (kept for parity)
from billing.models import Customer, Notification, SystemLog, Payment
from billing.customer_state import network_visibility

ALERT_THRESHOLD = 1


def sweep_expiry():
    now = timezone.now()

    past_due = Customer.objects.filter(
        expires_at__lte=now,
        status="active",
        installation_status="installed",
    ).exclude(status__in=["pending", "closed_not_installed"])

    total = past_due.count()

    # Split by whether we can actually see them online.
    network_visible, connected = network_visibility()
    online = 0
    if network_visible and connected:
        online = past_due.filter(pppoe_username__in=connected).count()

    no_expiry = Customer.objects.filter(
        expires_at__isnull=True, installation_status="installed"
    ).count()

    renewed = 0
    for c in past_due:
        price = c.plan.price if c.plan else 0
        if price and c.outstanding_balance <= -price:
            from billing.views import calculate_new_expiration_date

            new_expiry = calculate_new_expiration_date(
                c.expires_at, float(price), float(price)
            )
            c.expires_at = new_expiry
            c.outstanding_balance += price
            c.save(update_fields=["expires_at", "outstanding_balance"])
            Payment.objects.create(
                customer=c, username=c.pppoe_username,
                plan_name=c.plan.name if c.plan else None,
                amount=price, payment_method="advance_payment",
                reference_no="AUTO-RENEW",
                reason="Auto-renewed from Advance Payment wallet",
                expires_at=new_expiry, adjusted_by="System",
            )
            renewed += 1

    remaining = total - renewed

    if remaining >= ALERT_THRESHOLD:
        Notification.objects.create(
            title=f"{remaining} subscriber(s) past due",
            message=(
                f"{online} of them are still online. Open Customers and work the "
                f"\"Connected, Unpaid\" queue -- suspend deliberately, do not batch it."
                + (f" {no_expiry} installed customer(s) still have no expiry date."
                   if no_expiry else "")
            ),
            notification_type="billing",
            link="/customers/",
        )
        SystemLog.objects.create(
            table_name="Customer", record_id="0", action="EXPIRY_SWEEP",
            changed_by="System (Expiry Sweep)", target_name="expiry_sweep",
            old_data="", new_data=(
                f"past_due={total} renewed={renewed} online={online} no_expiry={no_expiry}"
            ),
        )

    return {
        "past_due": total, "renewed": renewed, "online": online,
        "no_expiry": no_expiry, "remaining": remaining,
        "network_visible": network_visible,
    }