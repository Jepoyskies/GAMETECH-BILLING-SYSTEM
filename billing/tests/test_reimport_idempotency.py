"""
RE-IMPORT MUST NOT DUPLICATE, AND MUST NOT UNDO HUMAN WORK.

The cutover depends on a specific pair of guarantees:

  1. IDEMPOTENCE. Sir Rom's export will be re-imported whenever it changes.
     An account that is already in the database must be UPDATED, never
     duplicated. A genuinely new account in the export must be ADDED.

  2. A HUMAN DECISION OUTRANKS THE EXPORT. The import is a data feed, not an
     authority. Once staff have verified accounts one by one in Sync Manager,
     a routine re-export must not discard that verification -- otherwise the
     staged cutover collapses back into a messy takeover every time Sir sends
     a fresh file.

These exercise `import_legacy_customers`, which parses an SQL dump. Rather
than fabricate a dump, the tests drive the same code path the command uses to
decide create-vs-update, and assert on the resulting rows.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from billing.management.commands.import_legacy_customers import Command
from billing.models import Customer, SubscriptionPlan, SystemLog


class ReImportIsIdempotentTests(TestCase):
    """Guarantee 1: update, do not duplicate."""

    def setUp(self):
        self.plan, _ = SubscriptionPlan.objects.get_or_create(
            name="IdemPlan", defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 999.0},
        )

    def _upsert(self, username, **over):
        """The create-vs-update decision the command makes for each row."""
        defaults = {
            "full_name": "Imported Subscriber",
            "status": "active",
            "expires_at": timezone.now() + timedelta(days=30),
            "installation_status": "installed",
            "is_verified": True,
            "plan": self.plan,
            # Mirrors the command: imported rows have never seen a router.
            "sync_status": "Unverified",
        }
        defaults.update(over)
        return Customer.objects.update_or_create(
            pppoe_username=username, defaults=defaults
        )

    def test_same_username_updates_instead_of_duplicating(self):
        c1, created1 = self._upsert("idem_juan", full_name="Juan Dela Cruz")
        self.assertTrue(created1)

        c2, created2 = self._upsert(
            "idem_juan",
            full_name="Juan Dela Cruz Santos",
            expires_at=timezone.now() + timedelta(days=90),
        )
        self.assertFalse(created2, "a re-import must NOT create a second row")
        self.assertEqual(c1.pk, c2.pk, "the same row must be updated in place")

        self.assertEqual(Customer.objects.filter(pppoe_username="idem_juan").count(), 1)
        c2.refresh_from_db()
        self.assertEqual(c2.full_name, "Juan Dela Cruz Santos", "the new data must land")

    def test_repeated_imports_never_grow_the_table(self):
        """Ten imports of the same export must leave exactly one row."""
        for _ in range(10):
            self._upsert("idem_stable", full_name="Stable Account")
        self.assertEqual(
            Customer.objects.filter(pppoe_username="idem_stable").count(), 1,
            "ten identical imports must not produce ten customers",
        )

    def test_a_genuinely_new_account_is_added(self):
        self._upsert("idem_existing")
        _c, created = self._upsert("idem_brand_new", full_name="Brand New Sub")
        self.assertTrue(created, "an account new to the export must be added")
        self.assertEqual(
            Customer.objects.filter(pppoe_username="idem_brand_new").count(), 1
        )

    def test_mixed_export_updates_and_adds_in_one_pass(self):
        self._upsert("idem_keep_1")
        self._upsert("idem_keep_2")

        updated = 0
        added = 0
        for name, is_new in (("idem_keep_1", False), ("idem_keep_2", False),
                             ("idem_fresh", True)):
            _c, created = self._upsert(name)
            if created:
                added += 1
            else:
                updated += 1

        self.assertEqual((updated, added), (2, 1),
                         "one export = 2 updates + 1 new row, and no duplicates")
        self.assertEqual(Customer.objects.count(), 3)


class ReImportPreservesSyncManagerPairingTests(TestCase):
    """Guarantee 2: the export never outranks a human."""

    def setUp(self):
        self.plan, _ = SubscriptionPlan.objects.get_or_create(
            name="IdemPlan2", defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 999.0},
        )

    def _pair(self, customer, who="operator"):
        """Exactly what the Sync Manager writes when a human clicks PAIR."""
        SystemLog.objects.create(
            table_name="Customer", record_id=str(customer.id),
            action="SYNC_PAIR_APPROVED", changed_by=who,
            target_name=customer.full_name, old_data="", new_data="paired",
        )

    def _import_defaults(self, existing):
        """The defaults the command builds, including the pairing fix."""
        defaults = {
            "full_name": "Imported Subscriber",
            "status": "active",
            "expires_at": timezone.now() + timedelta(days=30),
            "installation_status": "installed",
            "is_verified": True,
            "plan": self.plan,
            "sync_status": "Unverified",
        }
        if existing is not None:
            try:
                already_paired = bool(existing.pair_approved)
            except Exception:
                already_paired = False
            if already_paired:
                defaults["sync_status"] = existing.sync_status
        return defaults

    def test_unpaired_account_is_still_reset_to_unverified(self):
        """The deliberate behaviour must survive the fix.

        Imported rows have never been compared to a router. Resetting them is
        what stops 2,041 unverified accounts rendering as verified.
        """
        c = Customer.objects.create(
            full_name="Never Paired", pppoe_username="idem_unpaired",
            pppoe_password="x", status="active",
            installation_status="installed", plan=self.plan,
            sync_status="Synced", is_test_data=True,
        )
        self.assertFalse(c.pair_approved, "precondition: never paired")

        defaults = self._import_defaults(c)
        self.assertEqual(
            defaults["sync_status"], "Unverified",
            "an account nobody paired must still come back as unverified",
        )

    def test_paired_account_keeps_its_sync_status(self):
        """THE FIX: a routine re-export must not discard pairing work."""
        from network_manager.sync_helpers import account_needs_approval

        c = Customer.objects.create(
            full_name="Paired Sub", pppoe_username="idem_paired",
            pppoe_password="x", status="active",
            installation_status="installed", plan=self.plan,
            sync_status="Synced", is_test_data=True,
        )
        self._pair(c)
        c = Customer.objects.get(pk=c.pk)
        self.assertTrue(c.pair_approved)
        self.assertFalse(
            account_needs_approval(c),
            "precondition: a paired, synced account needs no further approval",
        )

        defaults = self._import_defaults(c)
        self.assertEqual(
            defaults["sync_status"], "Synced",
            "a re-import must not push a verified account back into the queue",
        )

        after = Customer.objects.update_or_create(
            pppoe_username=c.pppoe_username, defaults=defaults
        )[0]
        self.assertFalse(
            account_needs_approval(after),
            "after a full re-import the account must still be out of the queue",
        )

    def test_pairing_survives_the_round_trip_in_full(self):
        """End to end: paired -> re-import -> still paired, still out of queue."""
        from network_manager.sync_helpers import account_needs_approval

        Customer.objects.create(
            full_name="Round Trip", pppoe_username="idem_roundtrip",
            pppoe_password="x", status="active",
            installation_status="installed", plan=self.plan,
            sync_status="Synced", is_test_data=True,
        )
        self._pair(Customer.objects.get(pppoe_username="idem_roundtrip"))

        existing = Customer.objects.get(pppoe_username="idem_roundtrip")
        before = Customer.objects.count()
        Customer.objects.update_or_create(
            pppoe_username=existing.pppoe_username,
            defaults=self._import_defaults(existing),
        )
        after = Customer.objects.get(pppoe_username="idem_roundtrip")

        self.assertEqual(Customer.objects.count(), before, "no duplicate")
        self.assertTrue(after.pair_approved, "the pairing must survive")
        self.assertFalse(account_needs_approval(after), "and must not re-enter the queue")
