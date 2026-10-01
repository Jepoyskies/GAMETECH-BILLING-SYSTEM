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


def split_value_tuples(payload):
    """Split a mysqldump VALUES payload into individual "(...)" tuple strings.

    mysqldump emits extended inserts -- one INSERT line holding every row:
        INSERT INTO `t` VALUES ('1','a'),('2','b');
    A naive split on "," or "),(" corrupts any value containing those
    characters, so this walks the string tracking quote state and paren depth.
    Handles both \' and '' escaping.
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
            buf.append(ch)
            if ch == "\\" and i + 1 < n:          # backslash escape
                buf.append(payload[i + 1])
                i += 2
                continue
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
        """Yield (table_name, row_list) for every row in every INSERT statement.

        Handles both extended inserts (many tuples on one line, the mysqldump
        default) and one-tuple-per-line dumps.
        """
        with open(sql_file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                m = INSERT_RE.match(stripped)
                if not m:
                    continue
                vidx = stripped.upper().find("VALUES")
                if vidx == -1:
                    continue
                table = m.group(1)
                payload = stripped[vidx + len("VALUES"):].strip().rstrip(";").strip()
                for tup in split_value_tuples(payload):
                    row = self.parse_sql_line(tup)
                    if row:
                        yield table, row

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
            warned_shape = False

            # PASS 1: Read PPPoE credentials
            self.stdout.write(self.style.SUCCESS("Pass 1: Extracting PPPoE credentials..."))
            for table, row in self.iter_insert_rows(sql_file_path):
                if table == "pppoe_users" and len(row) >= 3:
                    pppoe_username = row[1]
                    pppoe_password = row[2]
                    if pppoe_username:
                        pppoe_creds[pppoe_username] = pppoe_password

            self.stdout.write(f"  Found {len(pppoe_creds)} PPPoE credentials")
            if not pppoe_creds:
                self.stdout.write(self.style.ERROR(
                    "  No PPPoE credentials found -- passwords will NOT be imported."
                ))

            # PASS 2: Import devices, account types, plans, and customers
            self.stdout.write(self.style.SUCCESS("Pass 2: Importing data..."))
            processed_customers = 0
            for table, row in self.iter_insert_rows(sql_file_path):
                    # Field mapping below is POSITIONAL (row[N]), so a dump with a
                    # different column count would either IndexError or silently
                    # shift values into the wrong fields. Pad to the expected width
                    # so short rows are safe, and shout once if the width is off.
                    if table == "customers":
                        if not warned_shape:
                            warned_shape = True
                            if len(row) != 27:
                                self.stdout.write(self.style.WARNING(
                                    f"  customers rows have {len(row)} columns, expected 27. "
                                    f"Field mapping is positional -- VERIFY the CREATE TABLE "
                                    f"column order before trusting this import."
                                ))
                        if len(row) < 27:
                            row = list(row) + [None] * (27 - len(row))

                    if table == "mikrotik_devices" and len(row) >= 6:
                        device_name = row[1]
                        ip_address = row[2]
                        if not dry_run:
                            device = self.get_or_create_device(
                                device_map, device_name, ip_address, row[3], row[4], row[5]
                            )
                            self.stdout.write(f"  Device: {device_name} ({'created' if device not in device_map.values() else 'exists'})")
                        else:
                            self.stdout.write(f"  [DRY] Would create device: {device_name}")

                    elif table == "account_type" and len(row) >= 2:
                        type_name = row[1]
                        if not dry_run:
                            acct = self.get_or_create_account_type(account_type_map, type_name)
                            self.stdout.write(f"  AccountType: {type_name}")
                        else:
                            self.stdout.write(f"  [DRY] Would create account type: {type_name}")

                    elif table == "service_plans" and len(row) >= 3:
                        # Legacy service_plans table - we use PLAN_MAPPING instead
                        pass

                    elif table == "customers" and len(row) >= 10:
                        processed_customers += 1
                        username = row[1]
                        full_name = row[5]
                        email = row[6] if row[6] else None
                        if email == "":
                            email = None

                        acct_type_str = row[2]
                        plan_name_str = row[3]
                        device_name_str = row[16] if len(row) > 16 else None

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
                        expires_at = self.parse_datetime_safe(row[4])
                        if expires_at:
                            expires_at = self.convert_timezone(expires_at)
                        else:
                            # Zero-date or NULL: flag for review, set expires_at=None
                            expires_at = None
                            zero_date_customers.append(username or full_name)

                        # Get PPPoE password
                        password = pppoe_creds.get(username, None)

                        # Parse status
                        status_val = str(row[9]).lower() if row[9] else "active"

                        # Generate portal password
                        portal_password = self.generate_portal_password()

                        if dry_run:
                            masked_user = username[:3] + "***" if username and len(username) > 3 else username
                            self.stdout.write(
                                f"  [DRY] Would import: {masked_user}, status={status_val}, "
                                f"expires={expires_at.strftime('%Y-%m-%d %H:%M') if expires_at else 'NONE (zero-date)'}, "
                                f"plan={plan_name_str}, device={device_name_str}"
                            )
                            continue

                        # Build defaults for update_or_create
                        defaults = {
                            "account_type": acct_obj,
                            "plan": plan_obj,
                            "mikrotik_device": device_obj,
                            "expires_at": expires_at,
                            "full_name": full_name,
                            "phone": row[7],
                            "address": row[8],
                            "status": status_val,
                            "created_at": self.parse_datetime_safe(row[10]) or timezone.now(),
                            "latitude": float(row[11]) if row[11] else None,
                            "longitude": float(row[12]) if row[12] else None,
                            "adjusted_by_router": row[13],
                            # row[14] (legacy `adjusted_by_referral`) has no matching
                            # field on the current Customer model -- deliberately dropped.
                            "sms_sent_at": self.parse_datetime_safe(row[17]),
                            "mac_address": row[18],
                            "referral_received": row[20] if row[20] else "",
                            "created_form_by": row[23] if row[23] else "",
                            "cignalplay_no": row[24],
                            "cignalplay_date": self.parse_date_safe(row[25]),
                            "cignalplay_adjustedby": row[26],
                            "pppoe_password": password,
                            "installation_status": "installed",
                            "installed_at": timezone.now(),
                            "is_verified": True,
                            # Hash-only storage (b756059). Storing the raw value in
                            # the legacy column would reintroduce plaintext passwords.
                            "portal_password_hash": make_password(portal_password),
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
