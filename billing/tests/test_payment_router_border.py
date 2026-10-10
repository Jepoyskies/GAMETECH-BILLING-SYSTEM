"""
The payment path is the last door to the router, and it is the one nobody
thinks of as a router door.

pay_customer_view -- the view behind the customer's own "Pay" button --
calls enable_pppoe_user, set_user_pppoe_profile and kick_active_user
directly. Every other router write in this project goes through the Sync
Manager pairing border, so the system reads as though they all do. This one
did not, and that is exactly why the gap survived review: it was invisible
by being the exception.

Found by driving the real view with a stub simulating ARMED router locks --
the condition under which the old code wrote. These tests freeze that
condition permanently, so a future refactor cannot quietly reopen it.

WHAT IS ASSERTED, AND WHY IT IS THE RIGHT ASSERTION
--------------------------------------------------
An UNCONNECTED customer paying must produce ZERO router writes while STILL
recording the payment. Not "refuse the payment". Money handed over at the
counter is real, and refusing to record it would mean taking cash with no
receipt, which is strictly worse than the problem being solved. The money
is always banked; only the router write waits.

And a CONNECTED customer paying must still write, with no false alarm --
otherwise the fix is just "break reactivation", which is not a fix.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import Customer, Payment, SubscriptionPlan, SystemLog


class _TripwireAPI:
    """A MikroTik client that records every write and claims to be LIVE.

    is_read_only = False is the whole point. Every other guard in the system
    is closed here on purpose, so a write can only be prevented by the
    pairing check itself. If a test passes because ROUTER_MODE blocked it,
    it has proved nothing about the border.
    """

    writes = []

    def __init__(self, *a, **k):
        self.is_read_only = False

    def enable_pppoe_user(self, *a, **k):
        _TripwireAPI.writes.append("enable")
        return {"success": True}

    def set_user_pppoe_profile(self, *a, **k):
        _TripwireAPI.writes.append("set_profile")
        return {"success": True}

    def kick_active_user(self, *a, **k):
        _TripwireAPI.writes.append("kick")
        return {"success": True}


def _plan():
    p, _ = SubscriptionPlan.objects.get_or_create(
        name="Payment Border Plan",
        defaults={"speed_mbps": 50, "speed_down": 50, "speed_up": 50,
                  "price": Decimal("500.00"), "router_profile": "default",
                  "validity_days": 30},
    )
    return p


class PaymentCannotWriteToAnUnconnectedRouter(TestCase):
    """The dangerous case: paying someone we have not connected."""

    def setUp(self):
        _TripwireAPI.writes = []
        self.admin = get_user_model().objects.create_user(
            username="payborder_admin", password="x", is_staff=True,
            is_superuser=True,
        )
        self.admin.set_password("payborder-admin-12345")
        self.admin.save()
        self.client.login(username="payborder_admin",
                          password="payborder-admin-12345")
        self.customer = Customer.objects.create(
            full_name="Payment Border",
            pppoe_username="payborder_%d" % Customer.objects.count(),
            pppoe_password="secret123",
            status="suspended",
            plan=_plan(),
            expires_at=timezone.now() - timedelta(days=5),
            is_test_data=True,
        )

    def _pay(self, reference):
        with patch("network_manager.services.MikrotikAPI", _TripwireAPI):
            return self.client.post(
                reverse("pay_customer", args=[self.customer.pppoe_username]),
                {"amount": "500.00", "payment_method": "CASH",
                 "reference_no": reference},
            )

    def _connect(self):
        SystemLog.objects.create(
            action="SYNC_PAIR_APPROVED", table_name="Customer",
            record_id=str(self.customer.id), changed_by=self.admin.username,
            target_name=self.customer.pppoe_username,
            changed_at=timezone.now(), new_data="connected",
        )
        self.customer.refresh_from_db()

    def test_paying_an_unconnected_customer_makes_no_router_write(self):
        """0 writes -- not 3. This is the assertion that matters."""
        self.customer.refresh_from_db()
        self.assertFalse(
            getattr(self.customer, "pair_approved", False),
            "precondition: a fresh account must NOT be connected",
        )
        self._pay("PB-1")
        self.assertEqual(
            _TripwireAPI.writes, [],
            "Paying a customer who is not connected reached the router: %s. "
            "Enabling a secret and kicking a live session for an account "
            "nobody has connected is the exact accident the Sync Manager "
            "border exists to prevent."
            % _TripwireAPI.writes,
        )

    def test_the_payment_is_still_recorded(self):
        """Never block the money. Only block the router."""
        before = Payment.objects.filter(customer=self.customer).count()
        self._pay("PB-2")
        after = Payment.objects.filter(customer=self.customer).count()
        self.assertEqual(
            after, before + 1,
            "The receipt must still be written. Money handed over at the "
            "counter is real; refusing to record it would mean taking cash "
            "with no record, which is worse than the problem being solved.",
        )

    def test_the_receipt_records_days_paid(self):
        """This path used to leave days_paid null while the other did not."""
        self._pay("PB-3")
        p = Payment.objects.filter(customer=self.customer).order_by("-id").first()
        self.assertIsNotNone(p.days_paid,
                             "days_paid must be recorded on this path too; "
                             "the Statement of Account renders it.")


class ConnectedCustomerPaymentStillReachesTheRouter(TestCase):
    """The other half. Without this, the fix is just 'break reactivation'."""

    def setUp(self):
        _TripwireAPI.writes = []
        self.admin = get_user_model().objects.create_user(
            username="payok_admin", password="x", is_staff=True,
            is_superuser=True,
        )
        self.admin.set_password("payok-admin-12345")
        self.admin.save()
        self.client.login(username="payok_admin", password="payok-admin-12345")
        self.customer = Customer.objects.create(
            full_name="Payment OK",
            pppoe_username="payok_%d" % Customer.objects.count(),
            pppoe_password="secret123",
            status="suspended",
            plan=_plan(),
            expires_at=timezone.now() - timedelta(days=5),
            is_test_data=True,
        )
        SystemLog.objects.create(
            action="SYNC_PAIR_APPROVED", table_name="Customer",
            record_id=str(self.customer.id), changed_by=self.admin.username,
            target_name=self.customer.pppoe_username,
            changed_at=timezone.now(), new_data="connected",
        )
        self.customer.refresh_from_db()

    def test_a_connected_customers_payment_does_reach_the_router(self):
        self.assertTrue(getattr(self.customer, "pair_approved", False),
                        "precondition: this account IS connected")
        with patch("network_manager.services.MikrotikAPI", _TripwireAPI):
            self.client.post(
                reverse("pay_customer", args=[self.customer.pppoe_username]),
                {"amount": "500.00", "payment_method": "CASH",
                 "reference_no": "PB-OK"},
            )
        self.assertTrue(
            _TripwireAPI.writes,
            "A connected customer who pays must still be reactivated on the "
            "router. The pairing gate is not supposed to stop paying working "
            "-- it is only supposed to stop paying reaching someone we have "
            "not connected.",
        )

    def test_the_payment_is_recorded_too(self):
        before = Payment.objects.filter(customer=self.customer).count()
        with patch("network_manager.services.MikrotikAPI", _TripwireAPI):
            self.client.post(
                reverse("pay_customer", args=[self.customer.pppoe_username]),
                {"amount": "500.00", "payment_method": "CASH",
                 "reference_no": "PB-OK-2"},
            )
        self.assertEqual(Payment.objects.filter(customer=self.customer).count(),
                         before + 1)