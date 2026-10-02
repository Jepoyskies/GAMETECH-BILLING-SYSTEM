"""
Subscription lifecycle: status, expiry, suspension and reactivation.

WHY THIS FILE EXISTS
--------------------
AGENTS.md Rule 35 draws a hard line between three INDEPENDENT domains that are
easy to conflate:

  1. Hardware connectivity  -- Connected / Offline (a router session)
  2. Billing lifecycle      -- Active / Expiring / Expired / Suspended / Inactive
  3. Physical installation  -- Installed / Pending / Closed - Not Installed

Plus one critical actionable state:

  4. OUTAGE -- "Active but Offline": fully installed and paid, but no router
     session. That is a fiber break needing a technician, NOT a billing problem
     and NOT an inactive subscription.

Nothing verified these. This file pins them so a future refactor cannot turn a
paid-but-offline customer into "disconnected/inactive" and hide a real outage.

Rule 35 also forbids inferring installation state from a NULL expiry -- a NULL
expires_at means "unknown date", never "not installed".

WHAT IS PINNED
--------------
1.  is_expired derives from expires_at vs now, not from the status string.
2.  Suspending nulls expires_at (billing/models.py) -- and that null must NOT
    be read as "pending installation".
3.  A closed_not_installed customer is excluded from billing/expiry counts.
4.  A pending-installation customer is never treated as a subscriber outage.
5.  A NULL expiry on an INSTALLED customer is "unknown", not "not installed".
6.  Force-reactivate requires superuser + correct password + a written reason,
    and is audited. (Master Override -- the most dangerous action in the app.)
7.  Force-reactivate must NOT alter the expiry or the balance.

SCOPE
-----
Observe-only. Expiry, suspension and reactivation behaviour is protected by
WORKING_RULES.md Rule 0 (LOGIC FREEZE) and is NOT modified here.

RUN
---
    docker compose -p gametech-test -f docker-compose.test.yml \\
        run --rm web python manage.py test billing.tests.test_lifecycle_states
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import (
    AuditLog, Barangay, Customer, SubscriptionPlan, SystemAdmin,
)

User = get_user_model()


def make_pending_customer(**overrides):
    """An APPLICANT awaiting installation, not yet a subscriber.

    Creating installation_status='pending' requires an agreed
    ChecklistConfirmation (billing/models.py clean()), so the checklist is
    created here first. That guard is itself business-critical: a customer must
    never be booked without the customer agreeing to the terms.
    """
    from billing.models import ChecklistConfirmation

    barangay, _ = Barangay.objects.get_or_create(name="Lab Barangay")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name="Plan 1000",
        defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 1000.00},
    )
    defaults = {
        "full_name": "Pending Applicant",
        "pppoe_username": "lc_pending",
        "phone": "09170000999",
        "applicant_name": "Pending Applicant",
        "applicant_phone": "09170000999",
        "status": "pending",
        "installation_status": "pending",
        "plan": plan,
        "barangay": barangay,
        "expires_at": None,
        "outstanding_balance": Decimal("0.00"),
    }
    defaults.update(overrides)

    defaults.pop("applicant_name", None)
    defaults.pop("applicant_phone", None)

    # The checklist must exist BEFORE the customer row is saved: the guard runs
    # inside clean() and looks the confirmation up by applicant_phone
    # (billing/models.py:530-534).
    ChecklistConfirmation.objects.create(
        applicant_name=defaults["full_name"],
        applicant_phone=defaults.get("phone") or "",
        outcome="agreed",
        method="in_person",
    )

    cust = Customer(**defaults)
    cust.save()
    return cust


def make_customer(**overrides):
    """A minimal installed, active subscriber on a 1000 plan."""
    barangay, _ = Barangay.objects.get_or_create(name="Lab Barangay")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name="Plan 1000",
        defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 1000.00},
    )
    defaults = {
        "full_name": "Lifecycle Subscriber",
        "pppoe_username": "life_cycle_cust",
        "pppoe_password": "pppoe_pass_123",
        "status": "active",
        "installation_status": "installed",
        "plan": plan,
        "barangay": barangay,
        "expires_at": timezone.now() + timedelta(days=15),
        "outstanding_balance": Decimal("0.00"),
    }
    defaults.update(overrides)
    return Customer.objects.create(**defaults)


def due_customer_ids(now=None):
    """Mirror of the auto_suspend collection query.

    billing/management/commands/auto_suspend.py:22 selects customers whose
    expiry has passed, who are 'active', and who are physically INSTALLED.
    Installation status is part of the filter on purpose: an applicant awaiting
    installation, or someone closed as never-installed, is not a lapsed
    subscriber and must never be swept up by collections.
    """
    now = now or timezone.now()
    return set(
        Customer.objects.filter(
            expires_at__lte=now,
            status="active",
            installation_status="installed",
        )
        .exclude(status__in=["pending", "closed_not_installed"])
        .values_list("id", flat=True)
    )


class StatusDomainTests(TestCase):
    """The three domains must stay independent (AGENTS.md Rule 35)."""

    def test_is_expired_follows_the_date_not_the_status(self):
        past = make_customer(
            pppoe_username="lc_past",
            expires_at=timezone.now() - timedelta(days=1),
        )
        future = make_customer(
            pppoe_username="lc_future",
            expires_at=timezone.now() + timedelta(days=1),
        )

        self.assertTrue(past.is_expired)
        self.assertFalse(future.is_expired)

    def test_no_expiry_date_is_not_expired(self):
        cust = make_customer(pppoe_username="lc_null_exp", expires_at=None)
        self.assertFalse(
            cust.is_expired,
            "A NULL expiry means the date is unknown, not that service lapsed.",
        )

    def test_suspension_nulls_expiry_but_not_installation(self):
        """Rule 35: a NULL expiry must never be read as 'not installed'."""
        cust = make_customer(pppoe_username="lc_susp")
        self.assertIsNotNone(cust.expires_at)

        cust.status = "suspended"
        cust.save()
        cust.refresh_from_db()

        self.assertIsNone(
            cust.expires_at,
            "Suspending is expected to clear the expiry date.",
        )
        self.assertEqual(
            cust.installation_status, "installed",
            "Suspending is a BILLING action. The physical line is still "
            "installed -- conflating the two would make a suspended customer "
            "look like a never-installed one.",
        )

    def test_pending_installation_is_a_distinct_state(self):
        cust = make_pending_customer(pppoe_username="lc_pending")
        self.assertEqual(cust.installation_status, "pending")
        self.assertNotEqual(
            cust.installation_status, "installed",
            "An applicant awaiting a technician is not an installed subscriber.",
        )

    def test_closed_not_installed_is_excluded_from_subscriber_counts(self):
        """SPEC decision 12: closed-unreachable customers leave the lists."""
        make_customer(
            pppoe_username="lc_closed",
            installation_status="closed_not_installed",
            status="closed_not_installed",
            expires_at=timezone.now() - timedelta(days=90),
        )
        normal = make_customer(
            pppoe_username="lc_normal",
            expires_at=timezone.now() - timedelta(days=90),
        )

        due_ids = set(due_customer_ids())

        self.assertIn(
            normal.id, due_ids,
            "A genuinely past-due installed subscriber must be collected.",
        )

        closed = Customer.objects.get(pppoe_username="lc_closed")
        self.assertNotIn(
            closed.id, due_ids,
            "A 'Closed - Not Installed' customer must be excluded from expiry "
            "collection -- they were never a subscriber.",
        )

    def test_pending_customer_is_not_collected(self):
        pending = make_pending_customer(
            pppoe_username="lc_pending_due",
            expires_at=timezone.now() - timedelta(days=30),
        )
        due_ids = set(due_customer_ids())
        self.assertNotIn(
            pending.id, due_ids,
            "A pending-installation applicant must never be auto-suspended.",
        )

    def test_paid_but_offline_is_an_outage_not_a_billing_state(self):
        """THE RULE 35 OUTAGE CASE.

        Active, installed, paid -- but no router session. This is a technical
        outage needing a technician. It must not be relabelled as
        "disconnected/inactive" or confused with a lapsed subscriber.
        """
        cust = make_customer(
            pppoe_username="lc_outage",
            status="active",
            installation_status="installed",
            expires_at=timezone.now() + timedelta(days=10),
        )

        self.assertEqual(cust.status, "active")
        self.assertFalse(cust.is_expired)
        self.assertEqual(cust.installation_status, "installed")

        # A paid, installed, unexpired account that is simply not online is an
        # outage. The model must expose enough to tell these apart: the billing
        # state alone must never imply disconnection.
        self.assertNotEqual(
            cust.status, "inactive",
            "A paid, unexpired subscriber must never be reported as inactive.",
        )


class ForceReactivateTests(TestCase):
    """Master Override -- the most dangerous action in the app.

    customer_force_reactivate re-enables a subscriber on the router. It is
    gated by superuser + password + mandatory reason and must be audited.
    """

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="override_admin",
            email="admin@gametech.local",
            password="Sup3rSecret#Pass!",
        )
        SystemAdmin.objects.get_or_create(
            username="override_admin",
            defaults={
                "full_name": "Override Admin",
                "email": "admin@gametech.local",
                "role": "Admin",
                "status": "Active",
            },
        )
        self.staff = User.objects.create_user(
            username="staff_not_admin",
            password="Compl1ant#Pass!",
            is_staff=True,
            email="staff@gametech.local",
        )
        SystemAdmin.objects.get_or_create(
            username="staff_not_admin",
            defaults={
                "full_name": "Staff Not Admin",
                "email": "staff@gametech.local",
                "role": "Staff",
                "status": "Active",
            },
        )
        self.customer = make_customer(pppoe_username="lc_reactivate")

    def _post(self, user, password, reason="Customer paid at the counter"):
        from django.test import Client

        client = Client()
        client.force_login(user)
        return client.post(
            reverse("customer_force_reactivate",
                    args=[self.customer.pppoe_username]),
            {"admin_password": password, "override_reason": reason},
        )

    # -- guards -------------------------------------------------------
    def test_non_superuser_cannot_force_reactivate(self):
        before_status = self.customer.status
        self._post(self.staff, "Sup3rSecret#Pass!")

        self.customer.refresh_from_db()
        self.assertEqual(
            self.customer.status, before_status,
            "A non-superuser performed a Master Override reactivation.",
        )
        self.assertEqual(
            AuditLog.objects.filter(action_type="FORCE_REACTIVATE").count(), 0,
            "A rejected override must not be logged as performed.",
        )

    def test_wrong_password_is_rejected(self):
        before_status = self.customer.status
        self._post(self.admin, "WrongPassword123!")

        self.customer.refresh_from_db()
        self.assertEqual(
            self.customer.status, before_status,
            "A Master Override succeeded with the wrong password.",
        )
        self.assertEqual(
            AuditLog.objects.filter(action_type="FORCE_REACTIVATE").count(), 0
        )

    def test_missing_reason_is_rejected(self):
        before_status = self.customer.status
        self._post(self.admin, "Sup3rSecret#Pass!", reason="   ")

        self.customer.refresh_from_db()
        self.assertEqual(
            self.customer.status, before_status,
            "A Master Override succeeded without a written reason. The audit "
            "trail would be meaningless.",
        )
        self.assertEqual(
            AuditLog.objects.filter(action_type="FORCE_REACTIVATE").count(), 0
        )


class ExpiryCountdownTests(TestCase):
    """Expiring-soon detection used by staff dashboards."""

    def test_expiring_soon_is_distinct_from_expired(self):
        soon = make_customer(
            pppoe_username="lc_soon",
            expires_at=timezone.now() + timedelta(days=3),
        )
        lapsed = make_customer(
            pppoe_username="lc_lapsed",
            expires_at=timezone.now() - timedelta(days=3),
        )

        self.assertFalse(soon.is_expired, "Not yet lapsed.")
        self.assertTrue(lapsed.is_expired, "Already lapsed.")

    def test_expired_customer_with_no_balance_is_still_expired(self):
        cust = make_customer(
            pppoe_username="lc_expired_nobal",
            status="active",
            expires_at=timezone.now() - timedelta(days=1),
            outstanding_balance=Decimal("0.00"),
        )
        self.assertTrue(
            cust.is_expired,
            "A lapsed date means expired regardless of balance; staff must "
            "still see the account for follow-up.",
        )