"""
Legacy import re-run (idempotency) tests.

WHY THIS FILE EXISTS
--------------------
The owner imports real subscriber data from a legacy MySQL dump and will
re-import a fresh export whenever the legacy system changes. The business
requirement is explicit and unambiguous:

    "Update existing, never duplicate."

These tests pin that behaviour so a future refactor of
``import_legacy_customers`` cannot quietly turn a re-import into a second
customer row, which would double-count subscribers on the billing counters.

SCOPE / SAFETY
--------------
These tests OBSERVE the import command. They never change how it behaves.
WORKING_RULES.md Rule 0 (LOGIC FREEZE) forbids altering payment, expiry,
reactivation or router-call behaviour; a test is the safe way to verify them.

RUN
---
    docker compose -p gametech-test -f docker-compose.test.yml \\
        run --rm web python manage.py test billing.tests.test_import_idempotency
"""

import tempfile
import unittest
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from billing.models import Customer

# A phpMyAdmin-style dump, which is the layout the real export uses:
#   INSERT INTO `t` (`c1`,`c2`) VALUES ('a','b'),('c','d');
CUSTOMER_COLUMNS = (
    "username", "full_name", "email", "phone", "address",
    "account_type", "plan_name", "device_name", "status",
    "expires_at", "created_at", "latitude", "longitude",
)


def _q(value):
    """Quote a python value the way the legacy dump stores it."""
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def build_dump(customers, pppoe_users=None, include_pppoe=True):
    """Build a minimal legacy SQL dump string.

    `customers` is a list of dicts keyed by CUSTOMER_COLUMNS.
    `pppoe_users` is a list of (username, password) tuples.
    """
    lines = []

    if include_pppoe:
        creds = pppoe_users or []
        if creds:
            vals = ",".join(
                "({},{})".format(_q(u), _q(p)) for u, p in creds
            )
            lines.append(
                "INSERT INTO `pppoe_users` (`username`,`password`) VALUES {};".format(vals)
            )

    for c in customers:
        vals = ",".join(_q(c.get(col)) for col in CUSTOMER_COLUMNS)
        lines.append(
            "INSERT INTO `customers` ({}) VALUES ({});".format(
                ",".join("`{}`".format(c) for c in CUSTOMER_COLUMNS), vals
            )
        )

    return "\n".join(lines) + "\n"


def write_dump(sql_text):
    """Write a dump to a temp file and return the path."""
    tmp = Path(tempfile.mkdtemp(prefix="gt_import_")) / "legacy_dump.sql"
    tmp.write_text(sql_text, encoding="utf-8")
    return str(tmp)


def sample_customer(**overrides):
    base = {
        "username": "gtacct01",
        "full_name": "Dela Cruz, Juan",
        "email": "juan@example.com",
        "phone": "09171234567",
        "address": "12 Mabini St, Cagayan de Oro",
        "account_type": "Residential",
        "plan_name": "Home 20",
        "device_name": None,
        "status": "active",
        "expires_at": "2026-12-01 00:00:00",
        "created_at": "2025-01-01 00:00:00",
        "latitude": None,
        "longitude": None,
    }
    base.update(overrides)
    return base


class ImportIdempotencyTests(TestCase):
    """Re-importing the same export must update, never duplicate."""

    def _import(self, sql_text):
        """Run the import command, capturing stdout instead of printing it."""
        from io import StringIO
        path = write_dump(sql_text)
        out = StringIO()
        call_command("import_legacy_customers", path, stdout=out)
        return out.getvalue()

    # ------------------------------------------------------------------
    # 1. First import creates the customer.
    # ------------------------------------------------------------------
    def test_first_import_creates_customer(self):
        sql = build_dump(
            [sample_customer()],
            pppoe_users=[("gtacct01", "secret123")],
        )
        self._import(sql)

        self.assertEqual(Customer.objects.count(), 1)
        cust = Customer.objects.get(pppoe_username="gtacct01")
        self.assertEqual(cust.full_name, "Dela Cruz, Juan")
        self.assertEqual(cust.pppoe_password, "secret123")

    # ------------------------------------------------------------------
    # 2. THE CORE REQUIREMENT: re-import updates, does not duplicate.
    # ------------------------------------------------------------------
    def test_reimport_does_not_duplicate(self):
        sql = build_dump(
            [sample_customer()],
            pppoe_users=[("gtacct01", "secret123")],
        )
        self._import(sql)
        self.assertEqual(Customer.objects.count(), 1)

        # Second run of the identical export.
        self._import(sql)

        self.assertEqual(
            Customer.objects.count(), 1,
            "Re-import duplicated the subscriber. The import must be idempotent "
            "on pppoe_username.",
        )

    # ------------------------------------------------------------------
    # 3. Changed fields are actually updated, not silently skipped.
    # ------------------------------------------------------------------
    def test_reimport_updates_changed_fields(self):
        self._import(build_dump(
            [sample_customer(phone="09171234567", address="12 Mabini St")],
            pppoe_users=[("gtacct01", "secret123")],
        ))
        cust = Customer.objects.get(pppoe_username="gtacct01")
        self.assertEqual(cust.phone, "09171234567")

        # New export: subscriber moved house, new number.
        self._import(build_dump(
            [sample_customer(
                phone="09189998888",
                address="88 Colon Ave, Cagayan de Oro",
                status="expired",
            )],
            pppoe_users=[("gtacct01", "secret123")],
        ))

        cust.refresh_from_db()
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(cust.phone, "09189998888", "Re-import did not update phone")
        self.assertEqual(cust.address, "88 Colon Ave, Cagayan de Oro")
        self.assertEqual(cust.status, "expired")

    # ------------------------------------------------------------------
    # 4. PPPoE password survives a re-import (customers must stay online).
    # ------------------------------------------------------------------
    def test_reimport_refreshes_pppoe_password_from_export(self):
        self._import(build_dump(
            [sample_customer()], pppoe_users=[("gtacct01", "oldpass")]
        ))
        self.assertEqual(
            Customer.objects.get(pppoe_username="gtacct01").pppoe_password, "oldpass"
        )

        self._import(build_dump(
            [sample_customer()], pppoe_users=[("gtacct01", "newpass")]
        ))
        self.assertEqual(
            Customer.objects.get(pppoe_username="gtacct01").pppoe_password, "newpass",
            "Re-import did not pick up a changed PPPoE password from the export.",
        )

    # ------------------------------------------------------------------
    # 5. Portal password hash is preserved -- a re-import must never
    #    invalidate a password a subscriber has already set.
    # ------------------------------------------------------------------
    def test_reimport_preserves_portal_password_hash(self):
        self._import(build_dump(
            [sample_customer()], pppoe_users=[("gtacct01", "secret123")]
        ))
        first_hash = Customer.objects.get(pppoe_username="gtacct01").portal_password_hash
        self.assertTrue(first_hash, "Import should generate a portal password hash")

        self._import(build_dump(
            [sample_customer(phone="09189998888")], pppoe_users=[("gtacct01", "secret123")]
        ))

        cust = Customer.objects.get(pppoe_username="gtacct01")
        self.assertEqual(
            cust.portal_password_hash, first_hash,
            "Re-import regenerated the portal password. Existing subscribers "
            "would be locked out of the customer portal.",
        )
        self.assertIsNone(
            cust.portal_password,
            "Raw portal password must never be stored (hash-only, b756059).",
        )

    # ------------------------------------------------------------------
    # 6. install date is preserved -- billing clock must not restart.
    # ------------------------------------------------------------------
    def test_reimport_preserves_installed_at(self):
        self._import(build_dump(
            [sample_customer()], pppoe_users=[("gtacct01", "secret123")]
        ))
        original = Customer.objects.get(pppoe_username="gtacct01").installed_at
        self.assertIsNotNone(original)

        self._import(build_dump(
            [sample_customer(phone="09189998888")], pppoe_users=[("gtacct01", "secret123")]
        ))

        cust = Customer.objects.get(pppoe_username="gtacct01")
        self.assertEqual(
            cust.installed_at, original,
            "Re-import reset installed_at. The billing clock and the agent "
            "60-day lock both key off this date.",
        )

    # ------------------------------------------------------------------
    # 7. A human review decision outranks the export.
    # ------------------------------------------------------------------
    def test_reimport_does_not_overwrite_reviewed_record(self):
        self._import(build_dump(
            [sample_customer(status="expired", expires_at="2020-01-01 00:00:00")],
            pppoe_users=[("gtacct01", "secret123")],
        ))
        cust = Customer.objects.get(pppoe_username="gtacct01")

        # A staff member corrects the record by hand. NOTE: the reviewed
        # status must NOT be "suspended" -- billing/models.py:558 deliberately
        # nulls expires_at whenever status is suspended, so a suspended row
        # with an expiry cannot be persisted in the first place.
        cust.status = "active"
        cust.expires_at = timezone.now() + timezone.timedelta(days=45)
        cust.legacy_reviewed_at = timezone.now()
        reviewed_expiry = cust.expires_at
        cust.save()

        # The stale export still claims the old values.
        self._import(build_dump(
            [sample_customer(status="expired", expires_at="2020-01-01 00:00:00")],
            pppoe_users=[("gtacct01", "secret123")],
        ))

        cust.refresh_from_db()
        self.assertEqual(
            cust.status, "active",
            "Re-import clobbered a status a human had reviewed.",
        )
        self.assertEqual(
            cust.expires_at, reviewed_expiry,
            "Re-import clobbered an expiry date a human had reviewed.",
        )

    # ------------------------------------------------------------------
    # 8. Dry run must not write anything at all.
    # ------------------------------------------------------------------
    def test_dry_run_writes_nothing(self):
        sql = build_dump(
            [sample_customer()], pppoe_users=[("gtacct01", "secret123")]
        )
        path = write_dump(sql)

        from io import StringIO
        out = StringIO()
        call_command("import_legacy_customers", path, dry_run=True, stdout=out)

        self.assertEqual(
            Customer.objects.count(), 0,
            "--dry-run wrote to the database. This is the flag the owner relies "
            "on to preview an export safely.",
        )

    # ------------------------------------------------------------------
    # 10. FIXED (owner-approved 2026-10-02): a re-import whose export omits
    # pppoe_users must never blank a working password.
    #
    # Previously the command wrote `pppoe_password: None` whenever the export
    # had no credential for an account, silently disconnecting paying
    # subscribers whose router secret depended on it. The command now keeps
    # the stored password and reports the affected accounts instead.
    # ------------------------------------------------------------------
    def test_reimport_does_not_wipe_pppoe_password_when_export_omits_it(self):
        self._import(build_dump(
            [sample_customer()], pppoe_users=[("gtacct01", "workingpass")]
        ))
        self.assertEqual(
            Customer.objects.get(pppoe_username="gtacct01").pppoe_password,
            "workingpass",
        )

        # New export arrived without any pppoe_users rows.
        self._import(build_dump([sample_customer()], include_pppoe=False))

        self.assertEqual(
            Customer.objects.get(pppoe_username="gtacct01").pppoe_password,
            "workingpass",
            "A re-import whose export omitted pppoe_users wiped the stored "
            "PPPoE password to NULL.",
        )

    # ------------------------------------------------------------------
    # 9. Multiple distinct subscribers all import cleanly.
    # ------------------------------------------------------------------
    def test_multiple_customers_import_and_rerun_is_idempotent(self):
        customers = [
            sample_customer(username="gtacct01", full_name="Dela Cruz, Juan"),
            sample_customer(username="gtacct02", full_name="Reyes, Maria",
                            email="maria@example.com"),
            sample_customer(username="gtacct03", full_name="Santos, Pedro",
                            email="pedro@example.com", status="expired"),
        ]
        creds = [("gtacct01", "p1"), ("gtacct02", "p2"), ("gtacct03", "p3")]
        sql = build_dump(customers, pppoe_users=creds)

        self._import(sql)
        self.assertEqual(Customer.objects.count(), 3)

        self._import(sql)
        self.assertEqual(
            Customer.objects.count(), 3,
            "Re-import duplicated subscribers in a multi-row export.",
        )
        self.assertEqual(Customer.objects.filter(pppoe_password="p2").count(), 1)