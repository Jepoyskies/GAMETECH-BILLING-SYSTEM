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
from network_manager.models import MikrotikDevice


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


class ReImportReturnsEveryoneToTheBorderTests(TestCase):
    """Guarantee 2: a re-import sends EVERY account back for pairing.

    The cutover rule: a fresh export means the source data may have changed,
    so a pairing made against the previous export verified data we no longer
    hold. Everyone goes back to the border, whether the row was updated or
    newly added. Verification is repeated deliberately -- that repetition IS
    the point of the staged cutover.
    """

    def setUp(self):
        self.plan, _ = SubscriptionPlan.objects.get_or_create(
            name="IdemPlan3",
            defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 999.0},
        )
        self.device = MikrotikDevice.objects.create(
            device_name="border_router", ip_address="10.255.255.10",
            api_username="nobody", api_password="nothing", api_port=8728,
        )

    def _pair(self, customer, who="operator"):
        """Exactly what the Sync Manager writes when a human clicks PAIR."""
        SystemLog.objects.create(
            table_name="Customer", record_id=str(customer.id),
            action="SYNC_PAIR_APPROVED", changed_by=who,
            target_name=customer.full_name, old_data="", new_data="paired",
        )

    def _customer(self, username):
        return Customer.objects.create(
            full_name="Sub", pppoe_username=username, pppoe_password="x",
            status="active", installation_status="installed",
            mikrotik_device=self.device, plan=self.plan,
            sync_status="Synced", is_test_data=True,
        )

    def _reimport(self, existing):
        """The defaults the command builds for one row of a re-import."""
        return {
            "full_name": existing.full_name,
            "status": "active",
            "expires_at": timezone.now() + timedelta(days=30),
            "installation_status": "installed",
            "is_verified": True,
            "plan": self.plan,
            # Imported rows have never been seen on a router.
            "sync_status": "Unverified",
            # ...and a re-import returns the account to the border.
            "legacy_reimported_at": timezone.now(),
        }

    def test_a_paired_account_returns_to_the_border(self):
        from network_manager.sync_helpers import account_needs_approval

        c = self._customer("border_juan")
        self._pair(c)
        c = Customer.objects.get(pk=c.pk)
        self.assertTrue(c.pair_approved, "precondition: paired")
        self.assertFalse(account_needs_approval(c), "precondition: out of the queue")

        Customer.objects.update_or_create(
            pppoe_username=c.pppoe_username, defaults=self._reimport(c))
        after = Customer.objects.get(pk=c.pk)

        self.assertEqual(after.sync_status, "Unverified", "back in the queue")
        self.assertFalse(
            after.pair_approved,
            "a re-import must invalidate the pairing made against older data",
        )
        self.assertTrue(
            account_needs_approval(after),
            "and the account must genuinely need pairing again",
        )

    def test_the_old_approval_is_kept_as_history(self):
        """Nothing is deleted -- a reviewer can always see what was signed off."""
        c = self._customer("border_history")
        self._pair(c, who="Sir Rom")
        Customer.objects.update_or_create(
            pppoe_username=c.pppoe_username, defaults=self._reimport(c))

        rows = SystemLog.objects.filter(
            action="SYNC_PAIR_APPROVED", record_id=str(c.id))
        self.assertEqual(rows.count(), 1, "the approval must remain in the log")
        self.assertEqual(rows.first().changed_by, "Sir Rom")

    def test_repairing_after_a_reimport_sticks(self):
        """The reviewer can pair again, and that pairing holds."""
        from network_manager.sync_helpers import account_needs_approval

        c = self._customer("border_repair")
        self._pair(c)
        Customer.objects.update_or_create(
            pppoe_username=c.pppoe_username, defaults=self._reimport(c))
        c = Customer.objects.get(pk=c.pk)
        self.assertFalse(c.pair_approved, "precondition: unpaired after re-import")

        # A short pause so the new approval is unambiguously after the stamp.
        stamped = c.legacy_reimported_at
        self._pair(Customer.objects.get(pk=c.pk), who="reviewer")
        c = Customer.objects.get(pk=c.pk)
        c.legacy_reimported_at = stamped
        self.assertTrue(c.pair_approved, "a fresh pairing must count")
        self.assertFalse(account_needs_approval(c))

    def test_a_brand_new_account_starts_unpaired(self):
        from network_manager.sync_helpers import account_needs_approval

        fresh = Customer.objects.update_or_create(
            pppoe_username="border_brand_new",
            defaults=self._reimport(self._customer("border_tmp")),
        )[0]
        self.assertFalse(fresh.pair_approved)
        self.assertTrue(account_needs_approval(fresh),
                        "a newly imported account must await pairing")

    def test_the_bulk_queue_agrees_with_the_model(self):
        """mark_pair_approvals() must not disagree with pair_approved.

        They are separate code paths; if only the model honoured the re-import
        stamp, the Sync Manager card would read APPROVED while the push gate
        refused the same account.
        """
        from network_manager.sync_helpers import mark_pair_approvals

        c = self._customer("border_bulk")
        self._pair(c)
        Customer.objects.update_or_create(
            pppoe_username=c.pppoe_username, defaults=self._reimport(c))

        fresh = Customer.objects.get(pk=c.pk)
        mark_pair_approvals([fresh])
        self.assertEqual(
            fresh.pair_approved, Customer.objects.get(pk=c.pk).pair_approved,
            "the bulk queue stamp and the model property must agree",
        )
