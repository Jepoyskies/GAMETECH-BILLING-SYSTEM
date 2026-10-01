import csv
import io
import json
import os
import re
import secrets
import string
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from billing.models import Customer, SubscriptionPlan, AccountType
from billing.signals import sync_customer_to_mikrotik
from network_manager.models import MikrotikDevice


# Legacy plan name -> current SubscriptionPlan name mapping
# Based on profiling of backup-2026-03-20_06-21-43.sql
PLAN_MAPPING = {
    'pppoe-20m': '20 Mbps Plan',
    'pppoe-50m': '50 Mbps Plan',
    'pppoe-30m': '30 Mbps Plan',
    'pppoe-15m_800': 'GTipid Fiber 1300',
    'pppoe-10m': '10Mbps',
    'pppoe-15m_700': 'GTipid Fiber 1000',
    'pppoe-50m-speedboost100': '50 Mbps Plan',
    'pppoe-100m': '100 Mbps Plan',
    'pppoe-50m_1300': 'GTipid Fiber 1300',
    'pppoe-50m_1200': 'GTipid Fiber 1300',
    'pppoe-15m_600': '5Mbps',
    'pppoe-30m_1200': '30 Mbps Plan',
    'pppoe-5m': '5Mbps',
    'pppoe-50m_1400': '50 Mbps Plan',
    'pppoe-30m-speedboost80': '30 Mbps Plan',
    'pppoe-200m': 'Business 200 Mbps',
    'pppoe-120m': 'Business 100 Mbps',
}

# Zero-date customers are flagged for review instead of given a default expiry

INSERT_RE = re.compile(r"^INSERT\s+INTO\s+`?([A-Za-z0-9_]+)`?")
COLUMN_LIST_RE = re.compile(r"^\s*\(([^)]*)\)\s*VALUES", re.I)
CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([A-Za-z0-9_]+)`?\s*\((.*?)\n\)\s*ENGINE",
    re.I | re.S,
)


def columns_from_create_table(sql_file_path):
    """Map table -> ordered column names, from the CREATE TABLE statements.

    Only needed as a fallback for dumps that omit the column list in their
    INSERT statements (plain mysqldump). phpMyAdmin dumps always include it.
    """
    cols = {}
    with open(sql_file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.lstrip().upper().startswith("CREATE TABLE"):
                continue
            # CREATE TABLE wraps across lines. Read until a line that is just the
            # closing paren -- stopping on the first ")" would trip over
            # "varchar(50)" and cut the block short.
            block = [line]
            while not re.search(r"^\s*\)\s*(ENGINE|;|$)", block[-1], re.M | re.I):
                nxt = f.readline()
                if not nxt:
                    break
                block.append(nxt)
            m = CREATE_TABLE_RE.search("".join(block))
            if not m:
                continue
            names = re.findall(r"^\s*`([A-Za-z0-9_]+)`", m.group(2), re.M)
            if names:
                cols[m.group(1)] = names
    return cols


def split_value_tuples(payload):
    """Split a mysqldump VALUES payload into individual "(...)" tuple strings.

    mysqldump emits extended inserts -- one INSERT line holding every row:
        INSERT INTO `t` VALUES ('1','a'),('2','b');
    A naive split on "," or "),(" corrupts any value containing those
    characters, so this walks the string tracking quote state and paren depth.
    Handles both MySQL backslash escaping and '' doubling. Returns tuples that
    are safe to hand to csv.reader.
    """
    tuples = []
    buf = []
    depth = 0
    in_str = False
    i = 0
    n = len(payload)
    while i < n:
        ch = payload[i]

        if in_str:
            if ch == "\\" and i + 1 < n:
                nxt = payload[i + 1]
                if nxt == "'":
                    # MySQL escapes an apostrophe as \'. Python's csv module knows
                    # nothing about MySQL escaping and would read that quote as a
                    # field/quote toggle, shattering "Eddie\'s Compound, ..." into
                    # four fields. Double it instead: csv then decodes it back to
                    # a single apostrophe. The backslash itself is dropped.
                    buf.append("''")
                else:
                    buf.append(nxt)
                i += 2
                continue
            buf.append(ch)
            if ch == "'":
                if i + 1 < n and payload[i + 1] == "'":   # doubled quote
                    buf.append(payload[i + 1])
                    i += 2
                    continue
                in_str = False
            i += 1
            continue

        if ch == "'":
            in_str = True
            buf.append(ch)
            i += 1
            continue

        if ch == "(":
            if depth == 0:
                buf = []
            depth += 1
            if depth > 1:
                buf.append(ch)
            i += 1
            continue

        if ch == ")":
            depth -= 1
            if depth == 0:
                tuples.append("(" + "".join(buf) + ")")
                buf = []
            else:
                buf.append(ch)
            i += 1
            continue

        if depth > 0:
            buf.append(ch)   # keep the commas separating values
        i += 1

    return tuples


class Command(BaseCommand):
    help = "Imports legacy customers from a MySQL dump file, preserving PPPoE credentials, status, and expiry dates."

    def add_arguments(self, parser):
        parser.add_argument("sql_file", type=str, help="Path to the legacy MySQL dump file")
        parser.add_argument(
            "--create-missing-plans",
            action="store_true",
            help="Create SubscriptionPlan records for legacy plans that don't exist in the current system",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database",
        )

    def iter_insert_rows(self, sql_file_path):
        """Yield (table_name, {column_name: value}) for every row in the dump.

        Handles both dump layouts:
          * mysqldump  -- ``INSERT INTO `t` VALUES (..),(..);`` all on one line
          * phpMyAdmin -- ``INSERT INTO `t` (`c1`,`c2`) VALUES`` then one
                         tuple per following line, terminated by ';'

        Rows are keyed by COLUMN NAME, never by position. The legacy schema
        gained a column mid-project (barangay_id at index 9), which silently
        shifted every positional field after it; name mapping makes that
        class of corruption impossible.
        """
        fallback_cols = columns_from_create_table(sql_file_path)

        with open(sql_file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                m = INSERT_RE.match(stripped)
                if not m:
                    continue
                table = m.group(1)

                # The column list (if any) sits AFTER `INSERT INTO `table``.
                after_table = stripped[m.end():]
                cm = COLUMN_LIST_RE.match(after_table)
                if cm:
                    names = [c.strip().strip("`") for c in cm.group(1).split(",")]
                    start = m.end() + cm.end()
                else:
                    names = fallback_cols.get(table)
                    vidx = stripped.upper().find("VALUES")
                    if vidx == -1 or not names:
                        continue
                    start = vidx + len("VALUES")

                # Tuples may continue on following lines (phpMyAdmin style).
                # Accumulate in a list: repeated string += on a multi-megabyte
                # statement is quadratic and will get the process OOM-killed.
                parts = [stripped[start:]]
                found_end = ";" in parts[0]
                while not found_end:
                    nxt = f.readline()
                    if not nxt:
                        break
                    nxt = nxt.rstrip()
                    parts.append(nxt)
                    found_end = ";" in nxt
                buffer = "\n".join(parts)

                payload = buffer.strip().rstrip(";").strip()
                for tup in split_value_tuples(payload):
                    values = self.parse_sql_line(tup)
                    if not values:
                        continue
                    if len(values) != len(names):
                        raise ValueError(
                            f"Table `{table}`: header lists {len(names)} columns "
                            f"but a row has {len(values)}. Dump is malformed -- "
                            f"refusing to import rather than guess."
                        )
                    yield table, dict(zip(names, values))

    def parse_sql_line(self, line):
        line = line.strip()
        if line.startswith("("):
            line = line[1:]
        if line.endswith(");"):
            line = line[:-2]
        elif line.endswith("),"):
            line = line[:-2]
        elif line.endswith(")"):
            # split_value_tuples() already balanced the parens, so a trailing ")"
            # here is always the tuple's own closing paren, never part of a value.
            line = line[:-1]

        reader = csv.reader(io.StringIO(line), quotechar="'", skipinitialspace=True)
        try:
            row = next(reader)
        except StopIteration:
            return []

        return [None if col == "NULL" else col for col in row]

    def parse_datetime_safe(self, dt_str):
        if not dt_str or dt_str.upper() == "NULL" or dt_str == "0000-00-00 00:00:00":
            return None
        dt = parse_datetime(dt_str)
        if dt and dt.tzinfo is None:
            return make_aware(dt)
        return dt

    def parse_date_safe(self, d_str):
        if not d_str or d_str.upper() == "NULL" or d_str == "0000-00-00":
            return None
        from django.utils.dateparse import parse_date
        return parse_date(d_str)

    def convert_timezone(self, dt):
        """Convert from UTC (legacy system) to UTC+8 (current system)."""
        if dt is None:
            return None
        # If the datetime is naive, assume it's UTC and convert to UTC+8
        if dt.tzinfo is None:
            dt = make_aware(dt)
        # Add 8 hours to convert from UTC to UTC+8
        return dt + timedelta(hours=8)

    def generate_portal_password(self):
        """Generate a secure random password for portal login."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(12))

    def get_or_create_device(self, device_map, device_name, ip_address, api_username, api_password, api_port):
        if device_name in device_map:
            return device_map[device_name]

        device, created = MikrotikDevice.objects.get_or_create(
            device_name=device_name,
            defaults={
                "ip_address": ip_address or "0.0.0.0",
                "api_username": api_username or "admin",
                "api_password": api_password or "",
                "api_port": api_port or "700",
            },
        )
        device_map[device_name] = device
        return device

    def get_or_create_account_type(self, account_type_map, type_name):
        if type_name in account_type_map:
            return account_type_map[type_name]

        obj, created = AccountType.objects.get_or_create(type_name=type_name)
        account_type_map[type_name] = obj
        return obj

    def get_or_create_plan(self, plan_map, legacy_plan_name, create_missing=False):
        if legacy_plan_name in plan_map:
            return plan_map[legacy_plan_name]

        # Try direct match first
        plan = SubscriptionPlan.objects.filter(name__iexact=legacy_plan_name).first()
        if plan:
            plan_map[legacy_plan_name] = plan
            return plan

        # Try mapped name
        mapped_name = PLAN_MAPPING.get(legacy_plan_name)
        if mapped_name:
            plan = SubscriptionPlan.objects.filter(name__iexact=mapped_name).first()
            if plan:
                plan_map[legacy_plan_name] = plan
                return plan

        # Create if flag is set
        if create_missing and legacy_plan_name:
            plan = SubscriptionPlan.objects.create(
                name=legacy_plan_name,
                price=0.00,
                validity_days=30,
                description=f"Auto-created from legacy import: {legacy_plan_name}",
            )
            plan_map[legacy_plan_name] = plan
            return plan

        return None

    def handle(self, *args, **kwargs):
        sql_file_path = kwargs["sql_file"]
        create_missing_plans = kwargs["create_missing_plans"]
        dry_run = kwargs["dry_run"]

        if not os.path.exists(sql_file_path):
            self.stdout.write(self.style.ERROR(f'File "{sql_file_path}" does not exist.'))
            return

        self.stdout.write(self.style.SUCCESS(f"Reading from {sql_file_path} ..."))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE — no database changes will be made."))

        # Disconnect the post_save signal to prevent router spam during import
        self.stdout.write(self.style.WARNING("Disconnecting Mikrotik post_save signals..."))
        post_save.disconnect(sync_customer_to_mikrotik, sender=Customer)

        try:
            plan_map = {}
            device_map = {}
            account_type_map = {}
            pppoe_creds = {}
            zero_date_customers = []

            # Parse the dump ONCE. Re-reading a multi-megabyte file three times
            # was slow enough to get the process killed on a 1 vCPU host.
            self.stdout.write(self.style.SUCCESS("Parsing dump..."))
            all_rows = list(self.iter_insert_rows(sql_file_path))
            self.stdout.write(f"  Parsed {len(all_rows)} rows from {sql_file_path}")

            # PASS 1: Read PPPoE credentials
            for table, row in all_rows:
                if table == "pppoe_users":
                    pppoe_username = row.get("username")
                    pppoe_password = row.get("password")
                    if pppoe_username:
                        pppoe_creds[pppoe_username] = pppoe_password

            self.stdout.write(f"  Found {len(pppoe_creds)} PPPoE credentials")
            if not pppoe_creds:
                self.stdout.write(self.style.ERROR(
                    "  No PPPoE credentials found -- passwords will NOT be imported."
                ))

            # PASS 2: Import devices, account types, plans, and customers
            self.stdout.write(self.style.SUCCESS("Importing data..."))
            processed_customers = 0

            # Devices FIRST. Rows arrive in file order and a dump happily emits
            # `customers` before `mikrotik_devices`, which would leave every
            # customer with mikrotik_device=NULL (and invisible to router sync).
            for table, row in all_rows:
                if table == "mikrotik_devices" and not dry_run:
                    self.get_or_create_device(
                        device_map,
                        row.get("device_name"),
                        row.get("ip_address"),
                        row.get("api_username"),
                        row.get("api_password"),
                        row.get("api_port"),
                    )
                elif table == "account_type" and not dry_run:
                    self.get_or_create_account_type(account_type_map, row.get("type_name"))

            if device_map:
                self.stdout.write(f"  Devices ready: {', '.join(device_map)}")

            for table, row in all_rows:
                    if table == "service_plans":
                        # Legacy service_plans table - we use PLAN_MAPPING instead
                        continue

                    elif table == "customers":
                        processed_customers += 1
                        username = row.get("username")
                        full_name = row.get("full_name")
                        email = row.get("email") or None
                        acct_type_str = row.get("account_type")
                        plan_name_str = row.get("plan_name")
                        device_name_str = row.get("device_name")

                        # Get or create related objects
                        if not dry_run:
                            acct_obj = self.get_or_create_account_type(account_type_map, acct_type_str) if acct_type_str else None
                            plan_obj = self.get_or_create_plan(plan_map, plan_name_str, create_missing_plans)
                            device_obj = device_map.get(device_name_str) if device_name_str else None
                            if not device_obj and device_name_str:
                                device_obj = MikrotikDevice.objects.filter(device_name=device_name_str).first()
                                if device_obj:
                                    device_map[device_name_str] = device_obj
                        else:
                            acct_obj = None
                            plan_obj = None
                            device_obj = None

                        # Parse and convert expiry
                        expires_at = self.parse_datetime_safe(row.get("expires_at"))
                        if expires_at:
                            expires_at = self.convert_timezone(expires_at)
                        else:
                            # Zero-date or NULL: flag for review, set expires_at=None
                            expires_at = None
                            zero_date_customers.append(username or full_name)

                        # Get PPPoE password
                        password = pppoe_creds.get(username, None)

                        # Parse status
                        raw_status = row.get("status")
                        status_val = str(raw_status).lower() if raw_status else "active"

                        # Portal password. PBKDF2 at ~1M iterations costs ~1s per
                        # customer, which is what made the first full import take 8
                        # minutes and destabilise the host. On a RE-import the
                        # account already has a hash, so keep it -- this turns a
                        # cutover-day re-import from minutes into seconds and
                        # never invalidates a portal password a customer has set.
                        lookup = (
                            {"pppoe_username": username}
                            if username
                            else {"full_name": full_name, "email": email}
                        )
                        existing = Customer.objects.filter(**lookup).only(
                            "id", "portal_password_hash", "installed_at"
                        ).first()

                        if dry_run:
                            masked_user = username[:3] + "***" if username and len(username) > 3 else username
                            self.stdout.write(
                                f"  [DRY] Would import: {masked_user}, status={status_val}, "
                                f"expires={expires_at.strftime('%Y-%m-%d %H:%M') if expires_at else 'NONE (zero-date)'}, "
                                f"plan={plan_name_str}, device={device_name_str}"
                            )
                            continue

                        # Build defaults for update_or_create
                        if existing and existing.portal_password_hash:
                            keep_portal_hash = existing.portal_password_hash
                        else:
                            keep_portal_hash = make_password(self.generate_portal_password())

                        defaults = {
                            "account_type": acct_obj,
                            "plan": plan_obj,
                            "mikrotik_device": device_obj,
                            "expires_at": expires_at,
                            "full_name": full_name,
                            "phone": row.get("phone"),
                            "address": row.get("address"),
                            "status": status_val,
                            "created_at": self.parse_datetime_safe(row.get("created_at")) or timezone.now(),
                            "latitude": float(row["latitude"]) if row.get("latitude") else None,
                            "longitude": float(row["longitude"]) if row.get("longitude") else None,
                            "adjusted_by_router": row.get("adjusted_by_router"),
                            # legacy `adjusted_by_referral` has no matching field on
                            # the current Customer model -- deliberately dropped.
                            "sms_sent_at": self.parse_datetime_safe(row.get("sms_sent_at")),
                            "mac_address": row.get("mac_address"),
                            "referral_received": row.get("referral_received") or "",
                            "created_form_by": row.get("created_form_by") or "",
                            "cignalplay_no": row.get("cignalplay_no"),
                            "cignalplay_date": self.parse_date_safe(row.get("cignalplay_date")),
                            "cignalplay_adjustedby": row.get("cignalplay_adjustedby"),
                            "pppoe_password": password,
                            "installation_status": "installed",
                            # Preserve the original install date across re-imports.
                            "installed_at": (existing.installed_at if existing and existing.installed_at else timezone.now()),
                            "is_verified": True,
                            # Hash-only storage (b756059). Storing the raw value in
                            # the legacy column would reintroduce plaintext passwords.
                            "portal_password_hash": keep_portal_hash,
                            "portal_password": None,
                            "sync_status": "Synced",
                        }

                        if username:
                            defaults["email"] = email
                            customer, created = Customer.objects.update_or_create(
                                pppoe_username=username, defaults=defaults
                            )
                        else:
                            defaults["pppoe_username"] = username
                            customer, created = Customer.objects.update_or_create(
                                full_name=full_name, email=email, defaults=defaults
                            )

                        if created:
                            self.stdout.write(f"  Created: {username or full_name}")
                        else:
                            self.stdout.write(f"  Updated: {username or full_name}")

            if processed_customers == 0:
                self.stdout.write(self.style.ERROR(
                    "NO customers were parsed out of this file. Nothing was imported. "
                    "Check that the dump contains an 'INSERT INTO `customers`' statement."
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Import complete! {processed_customers} customers processed."
                ))

            # Save import report for the web interface
            report = {
                "timestamp": timezone.now().isoformat(),
                "total_customers": processed_customers,
                "pppoe_credentials": len(pppoe_creds),
                "zero_date_customers": zero_date_customers,
                "devices_created": list(device_map.keys()),
                "plans_used": list(plan_map.keys()),
            }
            report_path = Path(__file__).parent.parent.parent / "data" / "last_import_report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2, default=str)
            self.stdout.write(f"  Import report saved to: {report_path}")

            if zero_date_customers:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n=== ZERO-DATE CUSTOMERS ({len(zero_date_customers)}) — NEED REVIEW ==="
                    )
                )
                for cust in zero_date_customers:
                    self.stdout.write(f"  - {cust}")
                self.stdout.write(
                    self.style.WARNING(
                        "These customers have no expiry date in the legacy system. "
                        "They have been imported with expires_at=NULL. "
                        "Review them in the import page."
                    )
                )

        finally:
            # Reconnect the signals
            self.stdout.write(self.style.WARNING("Reconnecting Mikrotik post_save signals..."))
            post_save.connect(sync_customer_to_mikrotik, sender=Customer)
