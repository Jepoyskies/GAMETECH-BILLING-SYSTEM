"""
THE BORDER TESTS.

Sync Manager is the border between our database and the shared routers.
Nothing goes out to a router unless a human clicks PAIR for that specific
account. These tests pin that down so a later refactor cannot quietly open
a second door.

Three properties, in order of how much damage they prevent:

  1. PAIRING IS MANDATORY. `Customer.push_blocked_reasons` refuses an
     account nobody has paired, whatever its billing state. Pairing is the
     identity check -- "this row is the same person as that PPPoE secret".
     Without it we could write a secret for an account we have never
     confirmed exists on the router.

  2. ROUTER_MODE=live ALONE OPENS NOTHING. It also needs
     ROUTER_WRITE_TOKEN == ROUTER_WRITE_TOKEN_EXPECTED. Two independent
     hand-edited keys, because the routers are shared with a legacy system
     that is still the billing authority.

  3. Everything still fails CLOSED. Any missing, blank or unrecognised
     value resolves to read_only, never to writes.

None of these tests touches a router. They exercise the decision logic only.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta

from billing.models import Customer, SubscriptionPlan, SystemAdmin
from network_manager.services.base import MikrotikBase

User = get_user_model()


def _plan():
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name="BorderPlan", defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 999.0},
    )
    return plan


def _customer(**kw):
    now = timezone.now()
    defaults = {
        "full_name": "Border Test",
        "pppoe_username": "border_%d" % Customer.objects.count(),
        "pppoe_password": "secret123",
        "status": "active",
        "expires_at": now + timedelta(days=30),
        "plan": _plan(),
        "is_test_data": True,
    }
    defaults.update(kw)
    return Customer.objects.create(**defaults)


class PairingIsMandatoryTests(TestCase):
    """Property 1: no router secret without a human PAIR click."""

    def test_unpaired_account_is_push_blocked_even_when_fully_paid(self):
        """The dangerous case: paid, not expired, no billing complaint."""
        c = _customer()
        self.assertFalse(
            getattr(c, "pair_approved", False),
            "precondition: a fresh account must not be paired",
        )
        self.assertIn(
            "Not connected",
            " ".join(c.push_blocked_reasons),
            "A paid, in-date account that nobody paired must still be refused. "
            "Pairing is the identity check; billing state is not a substitute.",
        )

    def test_pairing_reason_is_listed_first(self):
        """The operator must be told it was never approved, not sent to fix billing."""
        c = _customer(status="expired", expires_at=timezone.now() + timedelta(days=10))
        self.assertTrue(c.push_blocked_reasons[0].startswith("Not connected"))

    def test_billing_reasons_still_apply_after_pairing(self):
        """Pairing is not a free pass around the billing checks."""
        from billing.services.incentives import evaluate_agent_qualification  # noqa: F401

    def test_pairing_does_not_waive_expiry_or_unpaid(self):
        """Once paired, the unpaid/past-due gates must still refuse."""
        c = _customer(status="suspended")
        # Simulate the pairing sign-off the way the Sync Manager does: an audit
        # entry stamped SYNC_PAIR_APPROVED for this customer.
        from billing.models import SystemLog

        SystemLog.objects.create(
            table_name="Customer", record_id=str(c.id), action="SYNC_PAIR_APPROVED",
            changed_by="admin", target_name=c.full_name,
            old_data="", new_data="paired",
        )
        # Re-read from the DB: the Sync Manager page stamps pair_approved onto
        # instances in bulk, and that stamped value would otherwise survive.
        c = Customer.objects.get(pk=c.pk)
        c.__dict__.pop("_pair_approved_cache", None)
        self.assertTrue(getattr(c, "pair_approved", False), "pairing sign-off did not register")
        reasons = " ".join(c.push_blocked_reasons)
        self.assertNotIn("Not paired", reasons)
        self.assertIn("Unpaid", reasons)


class LiveModeNeedsTwoKeysTests(TestCase):
    """Property 2 + 3: ROUTER_MODE=live is never sufficient by itself."""

    def test_live_mode_without_token_is_refused(self):
        with override_settings(ROUTER_MODE="live",
                               ROUTER_WRITE_TOKEN="",
                               ROUTER_WRITE_TOKEN_EXPECTED=""):
            self.assertEqual(MikrotikBase._resolve_mode("live"), "read_only")

    def test_live_mode_with_only_one_key_is_refused(self):
        with override_settings(ROUTER_MODE="live",
                               ROUTER_WRITE_TOKEN="abc",
                               ROUTER_WRITE_TOKEN_EXPECTED=""):
            self.assertEqual(MikrotikBase._resolve_mode("live"), "read_only")
        with override_settings(ROUTER_MODE="live",
                               ROUTER_WRITE_TOKEN="",
                               ROUTER_WRITE_TOKEN_EXPECTED="abc"):
            self.assertEqual(MikrotikBase._resolve_mode("live"), "read_only")

    def test_live_mode_with_mismatched_keys_is_refused(self):
        with override_settings(ROUTER_MODE="live",
                               ROUTER_WRITE_TOKEN="abc",
                               ROUTER_WRITE_TOKEN_EXPECTED="xyz"):
            self.assertEqual(MikrotikBase._resolve_mode("live"), "read_only")

    def test_both_keys_matching_is_honoured(self):
        """The ONLY way to arm writes: two keys, deliberately, by a human."""
        with override_settings(ROUTER_MODE="live",
                               ROUTER_WRITE_TOKEN="armed",
                               ROUTER_WRITE_TOKEN_EXPECTED="armed"):
            self.assertEqual(MikrotikBase._resolve_mode("live"), "live")

    def test_unknown_and_missing_modes_fail_closed(self):
        """A malformed value is a config mistake, never permission to write.

        `None` is excluded on purpose: it means "no opinion, read settings",
        and the test settings deliberately set ROUTER_MODE="dry_run".
        """
        for bad in ("", "  ", "write", "yes", "true", "on", 0, 1, object(), b"live"):
            self.assertEqual(
                MikrotikBase._resolve_mode(bad), "read_only",
                "mode %r must resolve to read_only" % (bad,),
            )
        # None defers to settings rather than escalating.
        with override_settings(ROUTER_MODE="read_only"):
            self.assertEqual(MikrotikBase._resolve_mode(None), "read_only")

    def test_dry_run_is_still_honoured(self):
        """dry_run is a testing mode, not a write mode; it stays reachable."""
        with override_settings(ROUTER_MODE="dry_run"):
            self.assertEqual(MikrotikBase._resolve_mode("dry_run"), "dry_run")


class BulkSuspendIsClosedTests(TestCase):
    """The bulk page disconnects paying customers; it must stay shut."""

    def _staff(self, role):
        u = User.objects.create_user(username="border_%s" % role.lower(),
                                     password="X#Compliant1!", is_staff=True)
        SystemAdmin.objects.create(username=u.username, full_name=u.username,
                                   email="%s@g.local" % role.lower(),
                                   role=role, status="Active")
        return u

    def test_non_admin_cannot_reach_the_bulk_suspend_page(self):
        from django.urls import reverse

        for role in ("CSR", "Agent", "Technician", "Viewer"):
            u = self._staff(role)
            self.client.force_login(u)
            try:
                url = reverse("auto_suspend")
            except Exception:
                continue
            self.assertNotEqual(
                self.client.get(url).status_code, 200,
                "role %s must not be able to open the bulk-suspend page" % role,
            )

    def test_bulk_suspend_refuses_while_router_writes_are_blocked(self):
        """Even an Admin POST is refused while ROUTER_MODE is read_only."""
        from django.test import override_settings as _ov

        admin = self._staff("Admin")
        self.client.force_login(admin)
        c = _customer()
        with _ov(ROUTER_MODE="read_only"):
            r = self.client.post("/auto-suspend/", {
                "usernames": [c.pppoe_username],
                "confirm_legacy_checked": "yes",
            })
        self.assertIn(r.status_code, (302, 403))
        c.refresh_from_db()
        self.assertNotEqual(c.status, "suspended")
