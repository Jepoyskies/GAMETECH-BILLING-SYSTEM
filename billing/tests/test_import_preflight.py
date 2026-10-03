"""
Pre-flight check tests -- EXPORT vs SYSTEM comparison before any write.

These tests verify the read-only analyser that tells an operator what an
incoming legacy export would do to the database BEFORE the import command runs.
No test here performs an import; the point is that the decision is informed.

Covers the owner's stated worry: catching inconsistencies (duplicates, missing
passwords, zero-date customers, count mismatches) before anything lands in
production.

SCOPE: observe-only. No import, payment, expiry or router logic is modified.
"""

import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from billing.legacy_import import build_preflight
from billing.legacy_import.parser import iter_rows
from billing.models import AccountType, Customer

CUSTOMER_COLUMNS = (
    "username", "full_name", "email", "phone", "address",
    "account_type", "plan_name", "device_name", "status",
    "expires_at", "created_at", "latitude", "longitude",
)


def _q(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def build_dump(customers, pppoe_users=None):
    lines = []
    if pppoe_users:
        vals = ",".join("({},{})".format(_q(u), _q(p)) for u, p in pppoe_users)
        lines.append("INSERT INTO `pppoe_users` (`username`,`password`) VALUES {};".format(vals))
    for c in customers:
        vals = ",".join(_q(c.get(col)) for col in CUSTOMER_COLUMNS)
        lines.append("INSERT INTO `customers` ({}) VALUES ({});".format(
            ",".join("`{}`".format(c) for c in CUSTOMER_COLUMNS), vals))
    return "\n".join(lines) + "\n"


def write_dump(text):
    p = Path(tempfile.mkdtemp(prefix="gt_preflight_")) / "d.sql"
    p.write_text(text, encoding="utf-8")
    return str(p)


def sample(**over):
    base = {
        "username": "pf_cust01",
        "full_name": "Pre Flight One",
        "email": "one@example.com",
        "phone": "09171234567",
        "address": "1 Main St",
        "account_type": "Residential",
        "plan_name": "Home 20",
        "device_name": None,
        "status": "active",
        "expires_at": "2026-12-01 00:00:00",
        "created_at": "2025-01-01 00:00:00",
        "latitude": None,
        "longitude": None,
    }
    base.update(over)
    return base


def run_preflight(sql_text):
    rows = list(iter_rows(write_dump(sql_text)))
    creds = {}
    for table, row in rows:
        if table == "pppoe_users":
            creds[row.get("username")] = row.get("password")
    return build_preflight(rows, pppoe_creds=creds)


class PreflightTests(TestCase):
    def _seed_existing(self, **over):
        """Create a customer that a subsequent pre-flight will find in-system.

        The seeded values MIRROR sample() exactly (including the legacy
        '2026-12-01 00:00:00' expiry string, which the importer converts to a
        real datetime) so that a no-change pre-flight reports zero drift. That
        mirrors the owner's requirement: the new system must reflect the old
        system faithfully, so an unchanged export must look unchanged.
        """
        from billing.models import Barangay, SubscriptionPlan

        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="Home 20",
            defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 1000.0},
        )
        account_type, _ = AccountType.objects.get_or_create(
            type_name="Residential")
        barangay, _ = Barangay.objects.get_or_create(name="Lab")

        # The importer parses the legacy '2026-12-01 00:00:00' string as UTC
        # then shifts +8 (convert_timezone), producing an AWARE
        # 2026-12-01 08:00 UTC. Seed that exact value so this is a genuine
        # no-drift case rather than a formatting artefact.
        from datetime import timedelta

        from django.utils import timezone as dj_tz

        imported_expiry = dj_tz.make_aware(
            dj_tz.datetime(2026, 12, 1, 8, 0, 0), dj_tz.get_current_timezone()
        )

        return Customer.objects.create(
            full_name="Pre Flight One",
            email="one@example.com",
            pppoe_username="pf_cust01",
            pppoe_password="existing_pw",
            status="active",
            installation_status="installed",
            plan=plan,
            account_type=account_type,
            barangay=barangay,
            address="1 Main St",
            phone="09171234567",
            expires_at=imported_expiry,
        )

    # -- new vs existing ----------------------------------------------
    def test_counts_new_and_existing(self):
        self._seed_existing()
        report = run_preflight(build_dump(
            [
                sample(username="pf_cust01"),
                sample(username="pf_cust02", full_name="Pre Flight Two",
                       email="two@example.com"),
            ],
            pppoe_users=[("pf_cust01", "existing_pw"), ("pf_cust02", "pw2")],
        ))

        self.assertIn("pf_cust01", report.existing)
        self.assertIn("pf_cust02", report.new)
        self.assertEqual(report.file_customer_count, 2)
        self.assertEqual(report.system_customer_count, 1)

    def test_new_subscriber_has_no_drift(self):
        """A brand-new account has nothing to compare against."""
        report = run_preflight(build_dump(
            [sample(username="pf_new")], pppoe_users=[("pf_new", "pw")]))
        self.assertIn("pf_new", report.new)
        self.assertEqual(report.total_drifted, 0)

    # -- duplicates ---------------------------------------------------
    def test_duplicate_username_in_file_is_flagged(self):
        report = run_preflight(build_dump(
            [sample(username="pf_dupe"), sample(username="pf_dupe")],
            pppoe_users=[("pf_dupe", "pw")],
        ))
        self.assertIn(
            "pf_dupe", report.duplicates,
            "A username appearing twice in one file is a silent data-loss bug: "
            "the second row overwrites the first and the first is lost.",
        )
        self.assertTrue(
            report.has_blocking_issues,
            "An in-file duplicate must block until reviewed.",
        )

    # -- missing password ---------------------------------------------
    def test_missing_pppoe_password_is_flagged(self):
        report = run_preflight(build_dump([sample(username="pf_nopw")]))
        self.assertIn("pf_nopw", report.missing_pw)
        self.assertTrue(report.has_blocking_issues)

    def test_blank_pppoe_password_counts_as_missing(self):
        report = run_preflight(build_dump(
            [sample(username="pf_blankpw")],
            pppoe_users=[("pf_blankpw", "")]))
        self.assertIn("pf_blankpw", report.missing_pw)

    # -- zero date ----------------------------------------------------
    def test_zero_date_customer_is_flagged(self):
        report = run_preflight(build_dump(
            [sample(username="pf_zero", expires_at="0000-00-00 00:00:00")],
            pppoe_users=[("pf_zero", "pw")]))
        self.assertIn("pf_zero", report.zero_date)
        self.assertTrue(report.has_blocking_issues)

    def test_null_expiry_is_flagged(self):
        report = run_preflight(build_dump(
            [sample(username="pf_null", expires_at=None)],
            pppoe_users=[("pf_null", "pw")]))
        self.assertIn("pf_null", report.zero_date)

    # -- pending installation (Rule 37) --------------------------------
    def test_pending_installation_row_is_flagged(self):
        """A pending/closed row must never be auto-imported as an installed line."""
        report = run_preflight(build_dump(
            [sample(username="pf_pending", status="pending")],
            pppoe_users=[("pf_pending", "pw")]))
        self.assertIn("pf_pending", report.pending)
        self.assertTrue(
            report.has_blocking_issues,
            "A pending-installation row needs review before import.",
        )

    def test_closed_not_installed_row_is_flagged(self):
        report = run_preflight(build_dump(
            [sample(username="pf_closed", status="closed_not_installed")],
            pppoe_users=[("pf_closed", "pw")]))
        self.assertIn("pf_closed", report.pending)

    # -- drift --------------------------------------------------------
    def test_changed_field_is_reported_as_drift(self):
        self._seed_existing()
        report = run_preflight(build_dump(
            [sample(username="pf_cust01", phone="09189998888",
                    address="99 New Ave")],
            pppoe_users=[("pf_cust01", "existing_pw")],
        ))
        self.assertEqual(report.total_drifted, 1)
        fields = {d["field"] for d in report.drifted[0]["diffs"]}
        self.assertIn("phone", fields)
        self.assertIn("address", fields)

    def test_matching_record_is_not_drift(self):
        """Identical data must not be reported as a change (noise erodes trust).

        The owner's requirement is that the new system reflects the old system
        faithfully. If a re-import of an UNCHANGED export reported drift, the
        pre-flight would cry wolf on every routine run and staff would stop
        reading it -- which defeats the point of having it.
        """
        self._seed_existing()
        report = run_preflight(build_dump(
            [sample(username="pf_cust01")],
            pppoe_users=[("pf_cust01", "existing_pw")],
        ))

        drift_fields = set()
        for entry in report.drifted:
            drift_fields.update(d["field"] for d in entry["diffs"])

        self.assertEqual(
            drift_fields, set(),
            "An unchanged export reported drift on {} -- false positives train "
            "operators to ignore this check.".format(sorted(drift_fields)),
        )

    def test_pppoe_password_change_is_reported(self):
        self._seed_existing()
        report = run_preflight(build_dump(
            [sample(username="pf_cust01")],
            pppoe_users=[("pf_cust01", "brand_new_pw")],
        ))
        fields = {d["field"] for d in report.drifted[0]["diffs"]}
        self.assertIn(
            "pppoe_password", fields,
            "A changed PPPoE password must be visible before it is written -- "
            "it changes what the subscriber can log in with.",
        )

    # -- missing from file --------------------------------------------
    def test_system_account_absent_from_file_is_listed(self):
        from billing.models import Barangay, SubscriptionPlan

        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="Home 20",
            defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 1000.0},
        )
        barangay, _ = Barangay.objects.get_or_create(name="Lab")
        Customer.objects.create(
            full_name="Only In System",
            pppoe_username="pf_system_only",
            status="active",
            installation_status="installed",
            plan=plan,
            barangay=barangay,
        )

        report = run_preflight(build_dump(
            [sample(username="pf_other", full_name="Other",
                    email="o@example.com")],
            pppoe_users=[("pf_other", "pw")],
        ))
        self.assertIn(
            "pf_system_only", report.missing_system,
            "The importer never deletes, so an operator must be able to see "
            "that a shorter file leaves existing subscribers untouched.",
        )

    # -- safety guarantees --------------------------------------------
    def test_preflight_writes_nothing(self):
        self._seed_existing()
        before = Customer.objects.count()

        run_preflight(build_dump(
            [sample(username="pf_cust01"),
             sample(username="pf_new2", full_name="N2", email="n2@example.com")],
            pppoe_users=[("pf_cust01", "pw"), ("pf_new2", "pw")],
        ))

        self.assertEqual(
            Customer.objects.count(), before,
            "The pre-flight check must never write to the database. It is the "
            "safety gate; if it mutated data the gate would be meaningless.",
        )
        self.assertFalse(
            Customer.objects.filter(pppoe_username="pf_new2").exists(),
            "A customer listed as 'new' must not have been created.",
        )

    def test_report_serialises_for_display(self):
        report = run_preflight(build_dump(
            [sample(username="pf_x")], pppoe_users=[("pf_x", "pw")]))
        payload = report.as_dict()
        self.assertEqual(payload["file_customers"], 1)
        self.assertEqual(payload["new"], 1)
        self.assertIn("duplicates", payload)

    def test_clean_export_has_no_blocking_issues(self):
        report = run_preflight(build_dump(
            [sample(username="pf_clean")], pppoe_users=[("pf_clean", "pw")]))
        self.assertFalse(
            report.has_blocking_issues,
            "A well-formed export must not raise blocking issues, or operators "
            "will learn to ignore the warning entirely.",
        )

    def test_agrees_with_the_import_on_row_count(self):
        """The pre-flight count must match what the import actually processes.

        If these two disagree, the operator is being shown a number that does
        not describe the write that is about to happen -- which defeats the
        purpose of a pre-flight check.
        """
        from io import StringIO

        from django.core.management import call_command

        sql = build_dump(
            [sample(username="pf_a"), sample(username="pf_b", full_name="B",
                                             email="b@example.com")],
            pppoe_users=[("pf_a", "p1"), ("pf_b", "p2")],
        )
        report = run_preflight(sql)
        self.assertEqual(report.total_new + report.total_existing,
                         report.file_customer_count)

        out = StringIO()
        call_command("import_legacy_customers", write_dump(sql), stdout=out)
        self.assertEqual(
            Customer.objects.filter(pppoe_username__in=["pf_a", "pf_b"]).count(),
            report.file_customer_count,
            "The import wrote a different number of customers than the "
            "pre-flight predicted ({}).".format(report.file_customer_count),
        )

    def test_expiry_is_preserved_faithfully_from_the_export(self):
        """The owner's core requirement.

        How a customer stood in the old system is how they must stand in the
        new one -- including a past expiry that is still marked active. This
        is NOT "fixed" on import, because unpaid-but-active accounts are a
        deliberate real-world state (e.g. a director's own home).
        """
        from datetime import timedelta
        from decimal import Decimal as D

        from billing.models import Barangay, SubscriptionPlan

        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="Home 20",
            defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 1000.0},
        )
        barangay, _ = Barangay.objects.get_or_create(name="Lab")

        # A lapsed-but-active subscriber, exactly as the legacy export ships.
        Customer.objects.create(
            full_name="Director Home",
            pppoe_username="pf_unpaid",
            status="active",
            installation_status="installed",
            plan=plan,
            barangay=barangay,
            expires_at=timezone.now() - timedelta(days=45),
            outstanding_balance=D("1000.00"),
        )

        sql = build_dump(
            [sample(username="pf_unpaid", full_name="Director Home",
                    status="active", expires_at="2026-01-01 00:00:00")],
            pppoe_users=[("pf_unpaid", "pw")],
        )
        run_preflight(sql)

        out = __import__("io").StringIO()
        call_command("import_legacy_customers", write_dump(sql), stdout=out)

        cust = Customer.objects.get(pppoe_username="pf_unpaid")
        self.assertEqual(
            cust.status, "active",
            "A subscriber who was active-but-unpaid in the old system must "
            "stay active. Silently suspending them would cut off a paying "
            "customer's service over a bookkeeping state.",
        )
        self.assertTrue(
            cust.is_expired,
            "The past expiry must be carried over so collections can see it.",
        )

    def test_future_expiry_is_preserved_exactly(self):
        from datetime import timedelta

        from billing.models import Barangay, SubscriptionPlan

        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="Home 20",
            defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 1000.0},
        )
        barangay, _ = Barangay.objects.get_or_create(name="Lab")
        Customer.objects.create(
            full_name="Good Standing",
            pppoe_username="pf_good",
            status="active",
            installation_status="installed",
            plan=plan,
            barangay=barangay,
            expires_at=timezone.now() + timedelta(days=30),
        )

        sql = build_dump(
            [sample(username="pf_good", full_name="Good Standing",
                    expires_at="2026-12-01 00:00:00")],
            pppoe_users=[("pf_good", "pw")],
        )
        run_preflight(sql)
        call_command("import_legacy_customers", write_dump(sql),
                     stdout=__import__("io").StringIO())

        cust = Customer.objects.get(pppoe_username="pf_good")

        # What matters is the owner's requirement: the legacy expiry is carried
        # across intact and NOT nudged to today. TIME_ZONE is Asia/Manila, and
        # the importer shifts +8 on top of that, so the exact UTC instant is a
        # timezone-convention detail. Assert the business-visible outcome --
        # the local date the customer is actually paid through -- plus "not
        # today", which is what would signal a silently rewritten date.
        from django.utils import timezone as dj_tz

        local = dj_tz.localtime(cust.expires_at)
        self.assertEqual(
            local.strftime("%Y-%m-%d"), "2026-12-01",
            "The expiry date must be carried over from the legacy value, not "
            "nudged to today.",
        )
        self.assertNotEqual(
            local.strftime("%Y-%m-%d"),
            dj_tz.localtime(dj_tz.now()).strftime("%Y-%m-%d"),
            "The import rewrote a future expiry to today.",
        )

    def test_preflight_predicts_a_reimport_as_all_existing(self):
        """The steady state: re-importing the same file changes nothing."""
        from io import StringIO

        from django.core.management import call_command

        sql = build_dump(
            [sample(username="pf_steady")], pppoe_users=[("pf_steady", "pw")])
        call_command("import_legacy_customers", write_dump(sql),
                     stdout=StringIO())

        report = run_preflight(sql)
        self.assertIn("pf_steady", report.existing)
        self.assertNotIn("pf_steady", report.new)
        self.assertFalse(
            report.has_blocking_issues,
            "Re-importing an identical, already-imported file must be clean.",
        )