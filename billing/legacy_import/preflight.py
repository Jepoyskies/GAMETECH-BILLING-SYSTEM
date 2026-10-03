"""
Pre-flight comparison of an incoming legacy export against the live database.

WHY THIS EXISTS
---------------
The Sync Manager compares SYSTEM <-> ROUTER. That answers "is the line actually
provisioned?". Nothing compared EXPORT <-> SYSTEM, which is the gap this module
fills: before an import writes anything, an operator can see exactly what the
file would do to the database.

The owner described the workflow as: the export is the source of truth, the
routers are the other source of truth, and the system sits in the middle until
a human approves. This module is the "before" half of that approval -- it
reports, it never writes.

It is deliberately SEPARATE from import_legacy_customers. The import command
still does the writing; this only reads. That keeps the blast radius of a
mistake here at zero (see WORKING_RULES.md Rule 0, LOGIC FREEZE).

NO DATABASE WRITES. NO IMPORTS. Pure analysis.
"""

from collections import OrderedDict


def _get_attr(obj, dotted):
    """Read a possibly-dotted attribute path, returning None if absent."""
    cur = obj
    for part in dotted.split("."):
        if cur is None:
            return None
        cur = getattr(cur, part, None)
    return cur


def _norm_datetime(value):
    """Normalise an expiry to a naive UTC datetime, or None if unusable.

    The legacy file stores '2026-12-01 00:00:00' as a string. The importer
    parses it, assumes UTC, then shifts +8 (convert_timezone). Comparing the
    raw string to the stored datetime would report every single subscriber as
    drifted, which is exactly the kind of false alarm that trains an operator
    to ignore the warning.
    """
    from datetime import timedelta

    from django.utils.dateparse import parse_datetime
    from django.utils.timezone import make_aware

    if value is None or value == "":
        return None
    if hasattr(value, "tzinfo") or hasattr(value, "year"):
        dt = value
    else:
        text = str(value).strip()
        if not text or text.upper() == "NULL" or text.startswith("0000-00-00"):
            return None
        dt = parse_datetime(text)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = make_aware(dt)
        dt = dt + timedelta(hours=8)
    if dt.tzinfo is not None:
        from datetime import timezone as dt_timezone

        from django.utils import timezone as dj_tz

        dt = dj_tz.make_naive(dt, dt_timezone.utc)
    return dt.replace(microsecond=0)


def _norm_plan(value):
    """Plan names are compared case-insensitively and whitespace-trimmed."""
    if value is None:
        return None
    text = str(value).strip()
    return text.lower() or None


def _same(a, b, normaliser=None):
    """Loose equality so '1000.00' == '1000' and '' == None do not read as drift."""
    if normaliser is not None:
        a = normaliser(a)
        b = normaliser(b)
    if a is None or a == "":
        return b is None or b == ""
    if b is None or b == "":
        return a == ""
    return str(a).strip() == str(b).strip()


# Fields whose change would be visible to staff or would alter billing.
# sync_status is deliberately excluded: the importer always writes "Unverified"
# for a fresh import, and "Blocked"/"Synced" are router-side facts.
#
# (export column, dotted path on Customer, normaliser or None)
TRACKED_FIELDS = (
    ("full_name", "full_name", None),
    ("phone", "phone", None),
    ("address", "address", None),
    ("email", "email", None),
    ("status", "status", lambda v: str(v).strip().lower() if v else None),
    ("expires_at", "expires_at", _norm_datetime),
    ("plan_name", "plan.name", _norm_plan),
    ("account_type", "account_type.type_name", _norm_plan),
    ("device_name", "mikrotik_device.device_name", _norm_plan),
)


class PreflightReport:
    """Result of comparing an export against the database.

    Buckets are deliberately explicit rather than a single diff blob, because
    each one implies a DIFFERENT decision:

      new            -> will be created; check the count is what you expect
      existing       -> will be updated in place
      duplicates     -> appears twice IN THE FILE; last one silently wins
      drifted        -> fields that would change; read these before approving
      missing_pw     -> no usable PPPoE password in the file
      zero_date      -> no expiry in the file; imported with expires_at=NULL
      pending        -> installation_status pending/closed; must NOT be
                        auto-imported as an installed, billable line
      missing_system -> in the system but absent from this file (would be
                        untouched -- the importer never deletes)
    """

    def __init__(self):
        self.new = []
        self.existing = []
        self.duplicates = []
        self.drifted = []
        self.missing_pw = []
        self.zero_date = []
        self.pending = []
        self.missing_system = []
        self.file_customer_count = 0
        self.file_pppoe_count = 0
        self.system_customer_count = 0

    # -- summary ------------------------------------------------------
    @property
    def total_new(self):
        return len(self.new)

    @property
    def total_existing(self):
        return len(self.existing)

    @property
    def total_drifted(self):
        return len(self.drifted)

    @property
    def has_blocking_issues(self):
        """Issues an operator should consciously accept before importing."""
        return bool(
            self.duplicates
            or self.missing_pw
            or self.zero_date
            or self.pending
        )

    def as_dict(self):
        return OrderedDict(
            file_customers=self.file_customer_count,
            file_pppoe_users=self.file_pppoe_count,
            system_customers=self.system_customer_count,
            new=self.total_new,
            existing=self.total_existing,
            duplicates=self.duplicates,
            drifted=len(self.drifted),
            missing_password=self.missing_pw,
            zero_date=self.zero_date,
            pending_installation=self.pending,
            in_system_not_in_file=self.missing_system,
        )


def build_preflight(all_rows, pppoe_creds=None, plan_specs=None):
    """Compare parsed export rows against the live Customer table.

    `all_rows` is the (table_name, row_dict) list produced by
    billing.legacy_import.iter_rows. `pppoe_creds` maps username -> password.

    READ-ONLY: the only database access is a bulk SELECT of customers.
    """
    from django.db.models import Q

    from billing.models import Customer

    pppoe_creds = pppoe_creds or {}
    report = PreflightReport()

    file_rows = [r for t, r in all_rows if t == "customers"]
    report.file_customer_count = len(file_rows)
    report.file_pppoe_count = len(pppoe_creds)
    report.system_customer_count = Customer.objects.count()

    # Index the file by username so we can spot in-file duplicates.
    by_username = {}
    for row in file_rows:
        username = (row.get("username") or "").strip()
        if not username:
            continue
        if username in by_username:
            report.duplicates.append(username)
        else:
            by_username[username] = row

    if not by_username:
        return report

    # Bulk-load the matching customers (one query, not 2000).
    system_map = {}
    usernames = list(by_username)
    for chunk_start in range(0, len(usernames), 500):
        chunk = usernames[chunk_start:chunk_start + 500]
        for cust in Customer.objects.filter(
            pppoe_username__in=chunk
        ).select_related("plan", "account_type", "mikrotik_device"):
            system_map[cust.pppoe_username] = cust

    for username, row in by_username.items():
        cust = system_map.get(username)

        # Flag a file row whose installation state must not be assumed.
        inst = (row.get("installation_status") or "").strip().lower()
        status = (row.get("status") or "").strip().lower()
        if inst in ("pending", "closed_not_installed") or status in (
            "pending",
            "closed_not_installed",
        ):
            report.pending.append(username)

        # No usable password in the file.
        password = pppoe_creds.get(username)
        if not password:
            report.missing_pw.append(username)

        # No expiry in the file -> would import with expires_at=NULL.
        expires = (row.get("expires_at") or "").strip()
        if (not expires or expires.upper() == "NULL"
                or expires.startswith("0000-00-00")):
            report.zero_date.append(username)

        if cust is None:
            report.new.append(username)
            continue

        report.existing.append(username)

        # Work out which fields would change.
        diffs = []
        for export_key, dotted, normaliser in TRACKED_FIELDS:
            incoming = row.get(export_key)
            if isinstance(incoming, str):
                incoming = incoming.strip()
            current = _get_attr(cust, dotted)
            if not _same(incoming, current, normaliser):
                diffs.append({
                    "field": export_key,
                    "in_file": incoming if incoming not in (None, "") else None,
                    "in_system": current if current not in (None, "") else None,
                })

        # PPPoE password lives in the pppoe_users TABLE, not the customers
        # table, so it must be compared from `creds`. Leaving it in
        # TRACKED_FIELDS would read None from the customer row and report every
        # single subscriber as password-drifted -- pure noise that would train
        # an operator to ignore this check.
        if password and str(password) != str(cust.pppoe_password or ""):
            diffs.append({
                "field": "pppoe_password",
                "in_file": password,
                "in_system": cust.pppoe_password or None,
            })

        if diffs:
            report.drifted.append({"username": username, "diffs": diffs})

    # Accounts in the system that this file does not mention. The importer
    # never deletes, so these are simply untouched -- worth knowing so nobody
    # assumes a shorter file means those subscribers were removed.
    file_usernames = set(by_username)
    report.missing_system = list(
        Customer.objects.exclude(pppoe_username__in=file_usernames)
        .exclude(pppoe_username__isnull=True)
        .exclude(pppoe_username="")
        .values_list("pppoe_username", flat=True)[:500]
    )

    return report