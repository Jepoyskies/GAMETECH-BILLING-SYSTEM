"""
Payment -> receipt -> expiry -> reactivation tests.

WHY THIS FILE EXISTS
--------------------
Payments are the one workflow with ZERO coverage before this file, and the one
with real money attached. AGENTS.md Rule 39 requires that every monetary
transaction create a verified Payment receipt row and update the customer
balance, and forbids "floating counters without financial transaction
tracking". Nothing verified that.

These tests OBSERVE the payment view. They do not change how it behaves --
WORKING_RULES.md Rule 0 (LOGIC FREEZE) protects payments, expiry and
reactivation. A failing assertion here is a FINDING for the owner, not
something to "fix" by adjusting the view.

WHAT IS PINNED
--------------
1.  A payment always writes exactly one Payment receipt (no lost money).
2.  The receipt carries the new expiry and the recording staff member.
3.  A full-month payment extends the line by one month.
4.  A payment on an ALREADY LAPSED line anchors on today -- money taken,
    service live. (This is the bug calculate_new_expiration_date documents.)
5.  Outstanding debt is settled before time is bought.
6.  Overpayment beyond one month becomes advance credit, not lost money.
7.  Reactivating a suspended line flips status back to active.
8.  Agent 60-day lock is stamped on first payment.
9.  Invalid/zero/negative amounts are rejected and write NO receipt.
10. The whole thing is atomic: no receipt without the matching state change.

RUN
---
    docker compose -p gametech-test -f docker-compose.test.yml \\
        run --rm web python manage.py test billing.tests.test_payment_ledger
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import (
    Barangay, Customer, Payment, SubscriptionPlan, SystemAdmin,
)
from billing.views import calculate_new_expiration_date

User = get_user_model()


class PaymentLedgerTests(TestCase):
    """Cash integrity for the Pay Bill / Renew flow."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="cashier_ana",
            password="Compl1ant#Pass!",
            is_staff=True,
            email="ana@gametech.local",
        )
        # Views are behind @role_required, which resolves the role from
        # SystemAdmin (billing/decorators.py::_role_allows).
        SystemAdmin.objects.create(
            username="cashier_ana",
            full_name="Ana Cashier",
            email="ana@gametech.local",
            role="Staff",
            status="Active",
        )
        # pay_customer_view is gated by @permission_required("billing.add_payment")
        # (billing/views/payments/transactions.py:135), which raises 403 without
        # the permission -- a role alone is not enough to take money.
        add_payment = Permission.objects.filter(
            content_type__app_label="billing", codename="add_payment",
        ).first()
        self.assertIsNotNone(
            add_payment, "billing.add_payment permission must exist in the DB."
        )
        self.staff.user_permissions.add(add_payment)
        self.staff = get_user_model().objects.get(pk=self.staff.pk)

        self.client.force_login(self.staff)

        self.barangay = Barangay.objects.create(name="Lab Barangay")
        self.plan = SubscriptionPlan.objects.create(
            name="Plan 1000",
            speed_up="20 Mbps",
            speed_down="20 Mbps",
            price=1000.00,
        )
        self.customer = Customer.objects.create(
            full_name="Payment Test Subscriber",
            pppoe_username="pay_test_cust",
            pppoe_password="pppoe_pass_123",
            status="active",
            installation_status="installed",
            plan=self.plan,
            barangay=self.barangay,
            expires_at=timezone.now() + timedelta(days=10),
            outstanding_balance=Decimal("0.00"),
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _pay(self, amount, **extra):
        """POST a payment through the real view. Returns the response."""
        data = {
            "amount": amount,
            "payment_method": "cash",
            "reference_no": "TEST-REF-1",
            "reason": "Monthly subscription",
        }
        data.update(extra)
        return self.client.post(
            reverse("pay_customer", args=[self.customer.pppoe_username]),
            data,
        )

    # ------------------------------------------------------------------
    # 1. A payment must always leave a receipt. No silent money.
    # ------------------------------------------------------------------
    def test_payment_creates_exactly_one_receipt(self):
        self.assertEqual(Payment.objects.count(), 0)

        self._pay("1000")

        self.assertEqual(
            Payment.objects.count(), 1,
            "A successful payment must create exactly one Payment receipt. "
            "Cash taken with no receipt row means unaccounted money.",
        )
        payment = Payment.objects.get()
        self.assertEqual(float(payment.amount), 1000.0)
        self.assertEqual(payment.username, "pay_test_cust")
        self.assertEqual(payment.plan_name, "Plan 1000")
        self.assertEqual(payment.payment_method, "cash")
        self.assertEqual(payment.reference_no, "TEST-REF-1")
        self.assertEqual(
            payment.adjusted_by, self.staff.username,
            "The receipt must record which staff member took the money.",
        )
        self.assertIsNotNone(
            payment.paid_at, "A receipt must be dated (paid_at).",
        )

    # ------------------------------------------------------------------
    # 2. Receipt expiry must match the customer's new expiry.
    # ------------------------------------------------------------------
    def test_receipt_expiry_matches_customer_expiry(self):
        self._pay("1000")

        self.customer.refresh_from_db()
        payment = Payment.objects.get()

        self.assertEqual(
            payment.expires_at, self.customer.expires_at,
            "The receipt's expires_at must equal the customer's new expiry, "
            "otherwise the paper record and the live account disagree.",
        )

    # ------------------------------------------------------------------
    # 3. A full month extends a running line by one month.
    # ------------------------------------------------------------------
    def test_full_month_payment_extends_expiry_one_month(self):
        before = self.customer.expires_at
        self._pay("1000")
        self.customer.refresh_from_db()

        self.assertGreater(
            self.customer.expires_at, before,
            "A full-month payment must push the expiry forward.",
        )
        # ~30 days, allowing a day of slack for month-length arithmetic.
        delta_days = (self.customer.expires_at - before).days
        self.assertIn(
            delta_days, (29, 30, 31),
            "A one-month payment should extend the line by about a month; "
            "got {} days.".format(delta_days),
        )

    # ------------------------------------------------------------------
    # 4. THE IMPORTANT ONE: paying on a lapsed line must restore service.
    # ------------------------------------------------------------------
    def test_payment_on_expired_line_anchors_on_today(self):
        # Line lapsed a month ago.
        self.customer.expires_at = timezone.now() - timedelta(days=30)
        self.customer.status = "expired"
        self.customer.save()

        self._pay("1000")
        self.customer.refresh_from_db()

        self.assertGreater(
            self.customer.expires_at,
            timezone.now(),
            "A subscriber who paid must end up with a FUTURE expiry. "
            "Money was taken but service stayed cut.",
        )
        # and roughly one month out from today, not one month from the old date
        expected = add_months(timezone.now(), 1)
        self.assertAlmostEqual(
            self.customer.expires_at.timestamp(),
            expected.timestamp(),
            delta=3 * 86400,
            msg="A lapsed line should restart from today, not from the old "
                "expiry (that would hand back a date still in the past).",
        )

    # ------------------------------------------------------------------
    # 5. Reactivation: a suspended line comes back on payment.
    # ------------------------------------------------------------------
    def test_payment_reactivates_suspended_customer(self):
        self.customer.status = "suspended"
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, "suspended")

        self._pay("1000")
        self.customer.refresh_from_db()

        self.assertEqual(
            self.customer.status, "active",
            "A suspended customer who paid must be reactivated. "
            "Taking money while leaving them cut off is the worst outcome.",
        )

    def test_expired_customer_is_reactivated_by_payment(self):
        self.customer.status = "expired"
        self.customer.save()

        self._pay("1000")
        self.customer.refresh_from_db()

        self.assertEqual(
            self.customer.status, "active",
            "An expired customer who paid must be reactivated.",
        )

    # ------------------------------------------------------------------
    # 6. Debt is settled before new time is bought.
    # ------------------------------------------------------------------
    def test_outstanding_debt_is_settled_before_time(self):
        # Owes 400 from a previous partial/one-off charge.
        self.customer.outstanding_balance = Decimal("400.00")
        self.customer.save()
        before = self.customer.expires_at

        # Pays exactly the debt -- should NOT also buy a month of time.
        self._pay("400")
        self.customer.refresh_from_db()

        self.assertEqual(
            float(self.customer.outstanding_balance), 0.0,
            "The outstanding debt must be cleared by the payment.",
        )
        self.assertAlmostEqual(
            self.customer.expires_at.timestamp(),
            before.timestamp(),
            delta=86400,
            msg="A payment that only clears debt must not also extend the line.",
        )

    def test_partial_payment_clears_debt_then_extends_remainder(self):
        self.customer.outstanding_balance = Decimal("400.00")
        self.customer.save()
        before = self.customer.expires_at

        # Pays 1400: 400 clears debt, 1000 buys a month.
        self._pay("1400")
        self.customer.refresh_from_db()

        self.assertEqual(
            float(self.customer.outstanding_balance), 0.0,
            "Debt should be fully cleared.",
        )
        self.assertGreater(
            self.customer.expires_at, before,
            "The remainder after clearing debt should buy service time.",
        )

    # ------------------------------------------------------------------
    # 7. Overpayment becomes credit -- it must not vanish.
    # ------------------------------------------------------------------
    def test_overpayment_becomes_advance_credit(self):
        # Pays 3 months on a 1000 plan -> 2000 should sit as credit.
        self._pay("3000")
        self.customer.refresh_from_db()

        self.assertLess(
            float(self.customer.outstanding_balance), 0,
            "A 3-month payment on a 1-month plan must leave the extra 2000 as "
            "advance credit (negative balance), not evaporate. Got "
            "balance={!r}".format(self.customer.outstanding_balance),
        )
        # One month consumed for time, 2000 held as credit.
        self.assertAlmostEqual(
            float(self.customer.outstanding_balance), -2000.0, delta=1.0,
            msg="Expected 2000 of advance credit to remain.",
        )

    # ------------------------------------------------------------------
    # 8. Agent 60-day staggered-payment lock.
    # ------------------------------------------------------------------
    def test_first_payment_stamps_agent_lock_window(self):
        from billing.models import Agent

        agent = Agent.objects.create(
            name="Referring Agent",
            email="agent1@gametech.local",
            phone="09170000111",
        )
        self.customer.agent = agent
        self.customer.save()

        self.assertIsNone(
            self.customer.first_payment_date,
            "Precondition: no first payment recorded yet.",
        )

        self._pay("1000")
        self.customer.refresh_from_db()

        self.assertIsNotNone(
            self.customer.first_payment_date,
            "First payment must be dated -- the billing clock and the agent "
            "60-day lock both key off it.",
        )
        self.assertIsNotNone(
            self.customer.agent_lock_until,
            "An agent-referred customer's first payment must start the 60-day "
            "staggered-payment lock.",
        )
        lock_days = (self.customer.agent_lock_until.date()
                     - self.customer.first_payment_date).days
        self.assertEqual(lock_days, 60)

    def test_customer_without_agent_gets_no_lock(self):
        self._pay("1000")
        self.customer.refresh_from_db()

        self.assertIsNotNone(self.customer.first_payment_date)
        self.assertIsNone(
            self.customer.agent_lock_until,
            "A walk-in customer has no referring agent, so no 60-day lock.",
        )

    # ------------------------------------------------------------------
    # 9. Bad amounts must be refused and must not create a receipt.
    # ------------------------------------------------------------------
    def test_zero_amount_is_rejected_with_no_receipt(self):
        self._pay("0")
        self.assertEqual(
            Payment.objects.count(), 0,
            "A zero payment must not create a receipt.",
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, "active")

    def test_negative_amount_is_rejected_with_no_receipt(self):
        self._pay("-500")
        self.assertEqual(
            Payment.objects.count(), 0,
            "A negative payment must not create a receipt.",
        )

    def test_non_numeric_amount_is_rejected_with_no_receipt(self):
        self._pay("not-a-number")
        self.assertEqual(
            Payment.objects.count(), 0,
            "A non-numeric payment must not create a receipt.",
        )

    def test_non_numeric_amount_does_not_change_expiry(self):
        before = self.customer.expires_at
        self._pay("abc")
        self.customer.refresh_from_db()
        self.assertEqual(
            self.customer.expires_at, before,
            "A rejected payment must leave the expiry untouched.",
        )

    # ------------------------------------------------------------------
    # 10. One payment = one receipt, no double-write.
    # ------------------------------------------------------------------
    def test_single_post_creates_single_receipt(self):
        self._pay("1000")
        self.assertEqual(Payment.objects.count(), 1)

    def test_receipt_amount_matches_submitted_amount(self):
        for amount in ("500.00", "1500.50", "2500"):
            with self.subTest(amount=amount):
                Payment.objects.all().delete()
                self.customer.refresh_from_db()
                self._pay(amount)
                payment = Payment.objects.get()
                self.assertEqual(
                    float(payment.amount), float(amount),
                    "The receipt must record exactly what was collected.",
                )


class ExpirationMathTests(TestCase):
    """calculate_new_expiration_date -- the pure function behind every renewal."""

    def setUp(self):
        self.price = 1000.0

    def test_zero_price_returns_unchanged(self):
        exp = timezone.now() + timedelta(days=5)
        self.assertEqual(
            calculate_new_expiration_date(exp, 1000.0, 0.0), exp,
            "A free plan must not move the expiry.",
        )

    def test_zero_payment_returns_unchanged(self):
        exp = timezone.now() + timedelta(days=5)
        self.assertEqual(calculate_new_expiration_date(exp, 0.0, self.price), exp)

    def test_full_month_adds_one_month(self):
        anchor = timezone.now() + timedelta(days=10)
        result = calculate_new_expiration_date(anchor, self.price, self.price)
        self.assertAlmostEqual(
            result.timestamp(),
            add_months(anchor, 1).timestamp(),
            delta=2 * 86400,
        )

    def test_future_anchor_extends_from_existing_expiry(self):
        """An early renewal must not steal already-paid days."""
        anchor = timezone.now() + timedelta(days=20)
        result = calculate_new_expiration_date(anchor, self.price, self.price)
        self.assertGreater(
            result, anchor + timedelta(days=25),
            "A line with 20 days already paid must extend from its existing "
            "expiry, not restart from today.",
        )

    def test_lapsed_line_anchors_on_today(self):
        """THE BUG THIS FUNCTION EXISTS TO PREVENT.

        A customer four months behind pays one full month. Anchoring on the
        old expiry would hand back a date still three months in the past --
        cash taken, service still cut.
        """
        old_expiry = timezone.now() - timedelta(days=120)
        result = calculate_new_expiration_date(old_expiry, self.price, self.price)

        self.assertGreater(
            result, timezone.now(),
            "Paying on a long-lapsed line must produce a future expiry.",
        )
        self.assertAlmostEqual(
            result.timestamp(),
            add_months(timezone.now(), 1).timestamp(),
            delta=3 * 86400,
            msg="The new term should start now, not from the stale expiry.",
        )

    def test_naive_datetime_is_handled(self):
        naive = (timezone.now() + timedelta(days=10)).replace(tzinfo=None)
        result = calculate_new_expiration_date(naive, self.price, self.price)
        self.assertIsNotNone(result)
        self.assertGreater(result.timestamp(), timezone.now().timestamp())

    def test_partial_payment_grants_prorated_days(self):
        anchor = timezone.now() + timedelta(days=10)
        result = calculate_new_expiration_date(anchor, 500.0, self.price)
        delta = (result - anchor).days
        self.assertIn(
            delta, (14, 15, 16),
            "Half a month should grant ~15 days; got {}.".format(delta),
        )


def add_months(dt, n):
    """Local helper: add n calendar months, clamping short months."""
    import calendar
    year, month = dt.year, dt.month + n
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)