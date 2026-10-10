"""Regression tests for the two billing-axis bugs found during cutover QA.

Bug 1: payment_status keyed off status, so an applicant in 'pending' with a
       live expiry was badged Unpaid while demonstrably in date.

Bug 2: push_blocked_reasons only blocked the explicit unpaid statuses, so an
       'active' customer whose expiry had already passed could have a secret
       written for them or a pairing approved -- and approving one set
       sync_status='Synced', which rendered as a green APPROVED badge.

These pin the domain separation Rule 35 in AGENTS.md demands: status is
lifecycle/installation, expires_at is money.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from billing.models import Customer


def _counter():
    n = 0
    while True:
        n += 1
        yield n


_seq = _counter()


def make_customer(**kw):
    now = timezone.now()
    username = kw.pop("pppoe_username", None) or "test_sub_%d" % next(_seq)
    defaults = {
        "full_name": "Test Subscriber",
        "pppoe_password": "secret123",
        "status": "active",
        "expires_at": now + timedelta(days=30),
    }
    defaults.update(kw)
    status = defaults.get("status")

    # `Customer.save()` refuses to create or move an account to
    # 'Pending Installation' unless an agreed ChecklistConfirmation exists for
    # that phone. That guard is correct business logic -- it stops a line being
    # installed for someone who never agreed -- and it postdates this test. The
    # test is about the BILLING axis, so it satisfies the guard the legitimate
    # way rather than weakening it.
    if status == "pending":
        from django.contrib.auth import get_user_model

        from billing.models import ChecklistConfirmation

        # The guard matches on applicant_phone=self.phone, so the confirmation
        # and the customer must carry the SAME phone. This test does not pass
        # one, so give it one and use it for both -- otherwise the confirmation
        # is filed against "" while the customer has None and they never match.
        phone = defaults.get("phone") or "0917000%04d" % next(_seq)
        defaults["phone"] = phone

        # confirmed_by is a FK to User, not a free-text column -- it records
        # which staff member actually walked the applicant through the policy.
        who, _ = get_user_model().objects.get_or_create(
            username="checklist_staff",
            defaults={"is_staff": True},
        )
        ChecklistConfirmation.objects.create(
            applicant_phone=phone,
            outcome="agreed",
            confirmed_by=who,
        )

    return Customer.objects.create(pppoe_username=username, **defaults)


class PaymentStatusTests(TestCase):
    """Bug 1: the billing axis must not be driven by installation state."""

    def test_active_and_in_date_is_paid(self):
        c = make_customer(status="active")
        self.assertEqual(c.payment_status, "Paid")

    def test_applicant_with_live_expiry_is_paid_not_unpaid(self):
        """THE BUG: 'pending' means awaiting installation, not owing money."""
        c = make_customer(status="pending")
        self.assertEqual(
            c.payment_status,
            "Paid",
            "A pending applicant with a future expiry is in date. Badging them "
            "Unpaid conflates installation state with money.",
        )

    def test_past_due_is_unpaid(self):
        c = make_customer(status="active", expires_at=timezone.now() - timedelta(days=1))
        self.assertEqual(c.payment_status, "Unpaid")

    def test_no_expiry_is_unpaid(self):
        """No cut-off date means we cannot prove payment covers any period."""
        c = make_customer(expires_at=None)
        self.assertEqual(c.payment_status, "Unpaid")

    def test_explicit_lapsed_status_wins_over_a_future_expiry(self):
        for status in ("expired", "suspended", "pull out"):
            c = make_customer(status=status)
            self.assertEqual(
                c.payment_status,
                "Unpaid",
                "%s means the subscription is finished whatever the date says." % status,
            )


class PushGateTests(TestCase):
    """Bug 2: the money gate must catch a lapsed expiry, not just a status."""

    def test_active_but_past_due_is_blocked(self):
        c = make_customer(status="active", expires_at=timezone.now() - timedelta(days=3))
        self.assertTrue(
            c.is_push_blocked,
            "An active account whose expiry has passed has consumed more than "
            "it paid for. It must not get a router secret without an override.",
        )

    def test_past_due_reason_is_plain_english_with_the_date(self):
        c = make_customer(status="active", expires_at=timezone.now() - timedelta(days=3))
        joined = " ".join(c.push_blocked_reasons).lower()
        self.assertIn("past due", joined)

    def test_in_date_active_account_is_not_blocked(self):
        # An in-date, active account is clear on the BILLING axis -- that is
        # what this test is about. It is still refused on the identity axis,
        # because nobody paired it: no router secret may be written until a
        # human confirms in Sync Manager that this row is the same person as
        # that PPPoE secret. Pair it, and the billing axis is what remains.
        c = make_customer()
        self.assertEqual([r for r in c.push_blocked_reasons
                          if "Unpaid" in r or "Past due" in r], [],
                         "a paid, in-date account must be clear on billing")
        self.assertIn("Not connected",
                      " ".join(c.push_blocked_reasons))
        self.assertFalse(self._paired(c).is_push_blocked,
                         "once paired, an in-date active account must push")

    @staticmethod
    def _paired(customer):
        """Stamp the Sync Manager pairing sign-off and re-read the row."""
        from billing.models import SystemLog

        SystemLog.objects.create(
            table_name="Customer", record_id=str(customer.id),
            action="SYNC_PAIR_APPROVED", changed_by="operator",
            target_name=customer.full_name, old_data="", new_data="paired",
        )
        c = Customer.objects.get(pk=customer.pk)
        c.__dict__.pop("_pair_approved_cache", None)
        return c

    def test_missing_expiry_is_still_blocked(self):
        self.assertTrue(make_customer(expires_at=None).is_push_blocked)

    def test_reactivated_account_can_be_overridden(self):
        """An explicit 'expired' row stays overridable even before re-activation.

        This is why the gate checks status first instead of collapsing to
        payment_status: staff re-pay a lapsed line and then override, and must
        not be stranded while someone clicks Re-activate.
        """
        c = make_customer(status="expired")
        reasons = c.push_blocked_reasons
        self.assertTrue(reasons)
        self.assertTrue(any("Unpaid" in r for r in reasons))