"""
Legacy payment import tests.

THE GAP
-------
The export carries 12,571 payments. The importer originally had NO payment
handling, so production held a single seed Payment row. An empty ledger means
outstanding_balance is wrong for everyone, nobody has advance credit for
auto-suspend to renew, and the revenue reports show nothing.

WHAT IS PINNED
--------------
1. Payments are imported and linked to the right customer.
2. Re-importing the same export does NOT duplicate money (idempotent on the
   legacy id -- two identical payments on one day are legitimate, so no other
   key would do).
3. A payment whose username matches no customer is KEPT with a reason, not
   silently dropped. The cash was real.
4. Zero/negative amounts are skipped -- they are not revenue.
5. Legacy '0000-00-00' and 'NULL' dates become NULL, not year-1 timestamps.
6. Importing payments never changes a customer's status, expiry or balance.
   Rule 0: recalculating those is the owner's decision, not an import effect.
7. Dry run writes nothing.
8. Every run leaves an audit trail.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone

from billing.legacy_import import import_legacy_payments
from billing.models import Barangay, Customer, Payment, SubscriptionPlan, SystemLog

PAYMENT_COLUMNS = (
    "id", "username", "amount", "days", "expires_at", "paid_at",
    "payment_date_received", "payment_method", "reference_no",
    "reason", "plan_name", "adjusted_by", "mikrotik_devices", "created_at",
)


def payment_row(**over):
    base = {
        "id": "1001",
        "username": "legacy_sub01",
        "amount": "1000.00",
        "days": "30",
        "expires_at": "2026-01-09 17:43:00",
        "paid_at": "2025-12-25 17:44:44",
        "payment_date_received": "2025-12-25 17:44:44",
        "payment_method": "e-wallet",
        "reference_no": "1036156240906",
        "reason": "Monthly subscription",
        "plan_name": "pppoe-20m",
        "adjusted_by": "jeey2",
        "mikrotik_devices": "ccr2116.v1",
        "created_at": "2025-12-25 17:44:44",
    }
    base.update(over)
    return base


def as_rows(dicts):
    """Wrap dicts the way iter_rows yields them."""
    return [("payments", d) for d in dicts]


def make_customer(username="legacy_sub01", **over):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name="pppoe-20m",
        defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 700.0},
    )
    barangay, _ = Barangay.objects.get_or_create(name="Lab")
    defaults = {
        "full_name": "Legacy Subscriber",
        "pppoe_username": username,
        "pppoe_password": "pw",
        "status": "active",
        "installation_status": "installed",
        "plan": plan,
        "barangay": barangay,
        "expires_at": timezone.now() + timedelta(days=5),
        "outstanding_balance": Decimal("0.00"),
    }
    defaults.update(over)
    return Customer.objects.create(**defaults)


class PaymentImportTests(TestCase):
    def test_imports_and_links_the_payment(self):
        cust = make_customer()
        summary = import_legacy_payments(as_rows([payment_row()]))

        self.assertEqual(Payment.objects.count(), 1)
        pay = Payment.objects.get()
        self.assertEqual(pay.customer_id, cust.id)
        self.assertEqual(pay.username, "legacy_sub01")
        self.assertEqual(pay.amount, Decimal("1000.00"))
        self.assertEqual(pay.payment_method, "e-wallet")
        self.assertEqual(pay.reference_no, "1036156240906")
        self.assertEqual(summary["created"], 1)
        self.assertEqual(summary["matched_customers"], 1)

    def test_reimport_does_not_duplicate_money(self):
        """THE critical property. Re-running the export must not double-bill."""
        make_customer()
        rows = as_rows([payment_row(), payment_row(id="1002", amount="500.00")])

        first = import_legacy_payments(rows)
        self.assertEqual(first["created"], 2)
        self.assertEqual(Payment.objects.count(), 2)
        first_total = Payment.objects.aggregate(t=Sum("amount"))["t"]

        second = import_legacy_payments(rows)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["updated"], 2)
        self.assertEqual(
            Payment.objects.count(), 2,
            "Re-import duplicated payments. Money must never be counted twice.",
        )
        self.assertEqual(
            Payment.objects.aggregate(t=Sum("amount"))["t"], first_total,
            "The ledger total changed on re-import.",
        )

    def test_two_identical_payments_on_one_day_are_both_kept(self):
        """Two identical cash payments are legitimate -- so we key on the
        legacy id, never on amount+date."""
        make_customer()
        rows = as_rows([
            payment_row(id="2001"),
            payment_row(id="2002"),  # identical except the id
        ])
        import_legacy_payments(rows)
        self.assertEqual(Payment.objects.count(), 2)

    def test_orphan_payment_is_kept_not_dropped(self):
        """The cash was real even if the subscriber is gone."""
        make_customer()
        summary = import_legacy_payments(
            as_rows([payment_row(username="ghost_subscriber")]))

        self.assertEqual(Payment.objects.count(), 1)
        pay = Payment.objects.get()
        self.assertIsNone(pay.customer_id)
        self.assertEqual(pay.username, "ghost_subscriber")
        self.assertIn("no matching customer", pay.reason)
        self.assertEqual(summary["orphan_count"], 1)

    def test_zero_and_negative_amounts_are_skipped(self):
        make_customer()
        summary = import_legacy_payments(as_rows([
            payment_row(id="1", amount="0.00"),
            payment_row(id="2", amount="-500.00"),
            payment_row(id="3", amount="1000.00"),
        ]))
        self.assertEqual(summary["skipped_no_amount"], 2)
        self.assertEqual(Payment.objects.count(), 1)

    def test_unparseable_amount_is_skipped_not_crashed(self):
        make_customer()
        summary = import_legacy_payments(as_rows([
            payment_row(id="1", amount="not-a-number"),
        ]))
        self.assertEqual(summary["skipped_no_amount"], 1)
        self.assertEqual(Payment.objects.count(), 0)

    def test_legacy_null_dates_become_null(self):
        """'0000-00-00' must not become a year-1 timestamp that breaks
        date filters and sorting."""
        make_customer()
        import_legacy_payments(as_rows([payment_row(
            expires_at="0000-00-00 00:00:00",
            paid_at="NULL",
            payment_date_received="",
        )]))

        pay = Payment.objects.get()
        self.assertIsNone(pay.expires_at)
        self.assertIsNone(pay.paid_at)
        self.assertIsNone(pay.payment_date_received)

    def test_days_are_parsed(self):
        make_customer()
        import_legacy_payments(as_rows([payment_row(days="15")]))
        self.assertEqual(Payment.objects.get().days_paid, 15.0)

    def test_bad_days_do_not_crash(self):
        make_customer()
        import_legacy_payments(as_rows([payment_row(days="lots")]))
        self.assertIsNone(Payment.objects.get().days_paid)

    def test_empty_input_is_safe(self):
        summary = import_legacy_payments([])
        self.assertEqual(summary["seen"], 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_dry_run_writes_nothing(self):
        make_customer()
        summary = import_legacy_payments(
            as_rows([payment_row()]), dry_run=True)

        self.assertEqual(summary["seen"], 1)
        self.assertEqual(summary["created"], 0)
        self.assertEqual(
            Payment.objects.count(), 0,
            "A dry run must not create payments.",
        )
        self.assertGreater(summary["total_amount"], Decimal("0"))

    # -- Rule 0: never touch customer state ---------------------------
    def test_import_does_not_change_customer_status_expiry_or_balance(self):
        """Rule 0: recalculating balances is the owner's decision."""
        cust = make_customer(
            status="active",
            expires_at=timezone.now() + timedelta(days=5),
            outstanding_balance=Decimal("250.00"),
        )
        before = (
            cust.status, cust.expires_at, cust.outstanding_balance,
        )

        import_legacy_payments(as_rows([payment_row()]))

        cust.refresh_from_db()
        self.assertEqual(cust.status, before[0])
        self.assertEqual(cust.expires_at, before[1])
        self.assertEqual(cust.outstanding_balance, before[2])

    def test_import_writes_an_audit_trail(self):
        make_customer()
        import_legacy_payments(as_rows([payment_row()]))
        self.assertTrue(
            SystemLog.objects.filter(action="LEGACY_IMPORT").exists(),
            "A ledger import must leave a record an auditor can find.",
        )

    def test_audit_trail_mentions_orphans(self):
        make_customer()
        import_legacy_payments(as_rows([
            payment_row(username="ghost_one"),
        ]))
        log = SystemLog.objects.filter(action="LEGACY_IMPORT").first()
        self.assertIn("no matching customer", log.new_data)

    def test_legacy_id_is_recorded(self):
        make_customer()
        import_legacy_payments(as_rows([payment_row(id="9988")]))
        self.assertEqual(Payment.objects.get().legacy_id, "9988")

    def test_payments_without_a_legacy_id_still_import(self):
        """A file with no id column must not lose the money."""
        make_customer()
        row = payment_row()
        row.pop("id")
        summary = import_legacy_payments(as_rows([row]))
        self.assertEqual(summary["created"], 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertIsNone(Payment.objects.get().legacy_id)

    def test_large_batch_is_handled(self):
        """The real export has 12,571 rows; chunking must work."""
        make_customer()
        rows = as_rows([
            payment_row(id=str(i), amount="100.00") for i in range(1200)
        ])
        summary = import_legacy_payments(rows)
        self.assertEqual(summary["created"], 1200)
        self.assertEqual(Payment.objects.count(), 1200)
        self.assertEqual(
            Payment.objects.aggregate(t=Sum("amount"))["t"],
            Decimal("120000.00"),
        )

    def test_multiple_customers_each_get_their_own_payments(self):
        make_customer("sub_a")
        make_customer("sub_b")
        rows = as_rows([
            payment_row(id="1", username="sub_a", amount="500.00"),
            payment_row(id="2", username="sub_b", amount="700.00"),
            payment_row(id="3", username="sub_a", amount="500.00"),
        ])
        import_legacy_payments(rows)

        self.assertEqual(Payment.objects.filter(username="sub_a").count(), 2)
        self.assertEqual(Payment.objects.filter(username="sub_b").count(), 1)
        self.assertEqual(
            Payment.objects.aggregate(t=Sum("amount"))["t"], Decimal("1700.00"),
        )
        # And the distinct legacy ids prove they are not collapsed.
        self.assertEqual(Payment.objects.values("legacy_id").distinct().count(), 3)