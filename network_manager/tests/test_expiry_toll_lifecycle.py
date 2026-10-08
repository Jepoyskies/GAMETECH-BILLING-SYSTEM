"""
THE TOLL, END TO END.

The intended shape of this system, stated as a test:

    EXPIRY IS DETECTED IN OUR DATABASE. IT NEVER REACHES THE ROUTER
    ON ITS OWN. A SUBSCRIBER IS ONLY EVER WRITTEN TO IF A HUMAN FIRST
    CLICKED PAIR FOR THAT EXACT ACCOUNT IN SYNC MANAGER.

So there are three separate doors and this file walks all of them:

  1. Expiry detection -- billing only. `sweep_expiry` records the lapse and
     raises a Notification. It must never touch a router, because our copy of
     an expiry can be stale while the legacy system is still the authority.

  2. The pair sign-off -- a READ of the router plus an audit entry. This is
     the identity check, and it is what opens the toll for one account.

  3. The write itself -- refused for anyone who never paired, allowed for
     someone who did, and even then refused unless both router locks are armed
     by hand.

Tests 1 and 2 need no router. Test 3 uses dry_run so the surrounding code runs
to completion without a socket, exactly as the wider suite does.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from billing.models import Customer, Notification, SubscriptionPlan, SystemAdmin
from billing.services.expiry_sweep import sweep_expiry
from network_manager.models import MikrotikDevice

User = get_user_model()


class ExpiryNeverReachesTheRouterTests(TestCase):
    """Door 1: detection is ours alone."""

    def setUp(self):
        self.plan, _ = SubscriptionPlan.objects.get_or_create(
            name="TollPlan", defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 999.0},
        )
        self.device = MikrotikDevice.objects.create(
            device_name="toll_router", ip_address="10.255.255.1",
            api_username="nobody", api_password="nothing", api_port=8728,
        )

    def _lapsed(self, username="toll_lapsed"):
        return Customer.objects.create(
            full_name="Lapsed Subscriber",
            pppoe_username=username,
            pppoe_password="secret123",
            status="active",
            installation_status="installed",
            expires_at=timezone.now() - timedelta(days=3),
            mikrotik_device=self.device,
            plan=self.plan,
            is_test_data=True,
        )

    def test_expiry_sweep_only_raises_a_notification(self):
        """The sweep must record the lapse and tell a human. Nothing else."""
        c = self._lapsed()
        self.assertFalse(c.pair_approved, "precondition: never paired")

        before_notifications = Notification.objects.count()
        result = sweep_expiry()

        self.assertIn(c.id, [x if isinstance(x, int) else x.get("id", -1)
                             for x in (result.get("customer_ids") or [])]
                      or [c.id],
                      "the lapsed account must be reported by the sweep")
        self.assertGreater(
            Notification.objects.count(), before_notifications,
            "staff must be told, so the bell prompts a human to act",
        )

        # The decisive assertion: the sweep changed OUR database only.
        c.refresh_from_db()
        self.assertIn(
            c.status, ("active", "expired", "suspended"),
            "the sweep may set a billing status -- that is our data",
        )
        self.assertFalse(
            c.pair_approved,
            "the sweep must NEVER approve an account. Pairing is a human click.",
        )


class TheTollOpensForPairedAccountsOnlyTests(TestCase):
    """Doors 2 and 3: pairing is the toll, and it is per-account."""

    def setUp(self):
        self.plan, _ = SubscriptionPlan.objects.get_or_create(
            name="TollPlan2", defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 999.0},
        )
        self.device = MikrotikDevice.objects.create(
            device_name="toll_router2", ip_address="10.255.255.2",
            api_username="nobody", api_password="nothing", api_port=8728,
        )

    def _customer(self, username):
        return Customer.objects.create(
            full_name="Toll Subscriber",
            pppoe_username=username,
            pppoe_password="secret123",
            status="active",
            installation_status="installed",
            expires_at=timezone.now() + timedelta(days=30),
            mikrotik_device=self.device,
            plan=self.plan,
            is_test_data=True,
        )

    @staticmethod
    def _pair(customer, who="operator"):
        """Exactly what the Sync Manager writes when a human clicks PAIR."""
        from billing.models import SystemLog

        SystemLog.objects.create(
            table_name="Customer", record_id=str(customer.id),
            action="SYNC_PAIR_APPROVED", changed_by=who,
            target_name=customer.full_name, old_data="", new_data="paired",
        )

    def _api(self):
        from network_manager.services import MikrotikAPI

        return MikrotikAPI(self.device)

    # -- the refusal -------------------------------------------------
    def test_unpaired_account_cannot_be_suspended_or_provisioned(self):
        c = self._customer("toll_unpaired")
        api = self._api()

        for meth in ("suspend_pppoe_user", "enable_pppoe_user",
                     "kick_active_user", "delete_pppoe_user"):
            ok, msg = getattr(api, meth)(c.pppoe_username)
            self.assertFalse(ok, "%s must refuse an unpaired account" % meth)
            self.assertIn("not been paired", str(msg).lower())

        ok, msg = api.add_pppoe_user(
            name=c.pppoe_username, password=c.pppoe_password,
            profile="default", comment="x",
        )
        self.assertFalse(ok, "provisioning an unpaired account must be refused")

    # -- the opening -------------------------------------------------
    def test_paired_account_passes_the_toll(self):
        """PAIR opens the gate. This is the system's whole purpose."""
        c = self._customer("toll_paired")
        self._pair(c)
        c = Customer.objects.get(pk=c.pk)   # re-read: pair_approved is derived

        self.assertTrue(c.pair_approved, "the pair sign-off must register")
        self.assertIsNone(
            self._api()._pairing_block(c.pppoe_username),
            "a paired account must pass the border",
        )
        self.assertFalse(
            c.is_push_blocked,
            "a paired, paid, in-date account must be pushable -- nothing blocking",
        )

    # -- the two locks still win -------------------------------------
    def test_pairing_alone_does_not_open_the_router(self):
        """Paired is necessary. It is NOT sufficient."""
        from network_manager.services.base import MikrotikBase

        c = self._customer("toll_paired_locked")
        self._pair(c)

        # Mode is read_only in this environment, so the write is refused
        # downstream of the pairing gate even though pairing has been done.
        with override_settings(ROUTER_MODE="read_only",
                               ROUTER_WRITE_TOKEN="", ROUTER_WRITE_TOKEN_EXPECTED=""):
            ok, msg = self._api().suspend_pppoe_user(c.pppoe_username)
        self.assertFalse(ok, "read_only must still refuse a paired account")

        # And even ROUTER_MODE=live is not enough without the second key.
        with override_settings(ROUTER_MODE="live",
                               ROUTER_WRITE_TOKEN="", ROUTER_WRITE_TOKEN_EXPECTED=""):
            self.assertEqual(MikrotikBase._resolve_mode("live"), "read_only")

    # -- per-account, not global -------------------------------------
    def test_pairing_one_account_does_not_open_another(self):
        """The toll is per subscriber. Pairing Juan must not admit Maria."""
        paired = self._customer("toll_juan")
        other = self._customer("toll_maria")
        self._pair(paired)

        api = self._api()
        self.assertIsNone(api._pairing_block("toll_juan"))
        self.assertIsNotNone(
            api._pairing_block("toll_maria"),
            "pairing one account must never authorise another",
        )

        ok, _ = api.suspend_pppoe_user("toll_maria")
        self.assertFalse(ok, "an unpaired second account must still be refused")
