import json
import os
import secrets
import string
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db.models.signals import post_delete, post_save
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware

from billing.legacy_import import cutover_lines, iter_rows, resolve_plan
from billing.models import Customer, SubscriptionPlan, AccountType
from billing.signals import (
    delete_plan_on_mikrotik,
    sync_customer_to_mikrotik,
    sync_plan_on_save,
)
from network_manager.models import MikrotikDevice


# Legacy plan name -> current SubscriptionPlan name mapping
# Zero-date customers are flagged for review instead of given a default expiry
#
# There is deliberately NO legacy-plan mapping table here. Plans are resolved
# from the export's own service_plans rows (real speed + real price), and
# anything with no catalogue match is created from those same real numbers.
# A hand-maintained table was tried and it was wrong: the catalogue is a
# product matrix where GTipid and GIMI share a price at different speeds
# (P1,000 = GTipid 20 Mbps | GIMI 50 Mbps), so only (price, speed) identifies
# a product correctly.

class Command(BaseCommand):
    help = ("Imports legacy customers from a MySQL/phpMyAdmin dump, preserving PPPoE "
            "credentials, plans, status and expiry dates. Safe to re-run.")

    def add_arguments(self, parser):
        parser.add_argument("sql_file", type=str, help="Path to the legacy MySQL dump file")
        parser.add_argument(
            "--create-missing-plans",
            action="store_true",
            help="(No longer needed. Plans are always created from the export's own "
                 "speed and price. Flag kept so existing scripts still run.)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database",
        )

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

        # Disconnect the router sync signals. Every plan the import creates would
        # otherwise fire a save signal that tries to reach all routers, each with
        # a connection timeout -- that is what got the container OOM-killed.
        self.stdout.write(self.style.WARNING("Disconnecting Mikrotik sync signals..."))
        post_save.disconnect(sync_customer_to_mikrotik, sender=Customer)
        post_save.disconnect(sync_plan_on_save, sender=SubscriptionPlan)
        post_delete.disconnect(delete_plan_on_mikrotik, sender=SubscriptionPlan)

        try:
            plan_map = {}
            device_map = {}
            account_type_map = {}
            pppoe_creds = {}
            zero_date_customers = []

            # Parse the dump ONCE. Re-reading a multi-megabyte file three times
            # was slow enough to get the process killed on a 1 vCPU host.
            self.stdout.write(self.style.SUCCESS("Parsing dump..."))
            all_rows = list(iter_rows(sql_file_path))
            self.stdout.write(f"  Parsed {len(all_rows)} rows from {sql_file_path}")

            # The export is the source of truth. Build plan_name -> real
            # (speed, price) from the dump's own service_plans table so we match
            # on actual data instead of a hand-maintained guess table.
            plan_specs = {}
            for t, r in all_rows:
                if t == "service_plans" and r.get("plan_name"):
                    plan_specs[r["plan_name"]] = r
            self.stdout.write(f"  Plan catalogue from export: {len(plan_specs)} plans")

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
            created_count = 0
            updated_count = 0
            preserved_count = 0

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
                        # Handled up front: these rows are the plan catalogue.
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
                            plan_obj = resolve_plan(
                                plan_map, plan_name_str,
                                spec=plan_specs.get(plan_name_str),
                            )
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
                            "id", "portal_password_hash", "installed_at", "legacy_reviewed_at"
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

                        # A human decision always beats the export. If someone has
                        # reviewed this record, a re-import must not undo their work
                        # by resetting status or wiping an expiry date back to NULL.
                        if existing and existing.legacy_reviewed_at:
                            defaults["expires_at"] = existing.expires_at
                            defaults["status"] = existing.status
                            preserved_count += 1

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
                            created_count += 1
                        else:
                            updated_count += 1

            if processed_customers == 0:
                self.stdout.write(self.style.ERROR(
                    "NO customers were parsed out of this file. Nothing was imported. "
                    "Check that the dump contains an 'INSERT INTO `customers`' statement."
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Import complete! {processed_customers} customers processed."
                ))

            if not dry_run:
                for line in cutover_lines(created_count, updated_count, len(pppoe_creds), preserved_count):
                    self.stdout.write(line)

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
            self.stdout.write(self.style.WARNING("Reconnecting Mikrotik sync signals..."))
            post_save.connect(sync_customer_to_mikrotik, sender=Customer)
            post_save.connect(sync_plan_on_save, sender=SubscriptionPlan)
            post_delete.connect(delete_plan_on_mikrotik, sender=SubscriptionPlan)
