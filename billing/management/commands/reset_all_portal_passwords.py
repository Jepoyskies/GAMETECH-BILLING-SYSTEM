"""
Bulk-issue portal passwords so subscribers can actually log in.

WHY THIS EXISTS
---------------
`import_legacy_customers` deliberately gives every imported customer a RANDOM
portal password and keeps only the hash (`make_password(generate_portal_password())`).
That is correct for security -- we never ship a guessable credential -- but it
means that out of the box **no customer can log in**: the plaintext was
discarded at import and nobody, staff included, knows it.

This command is the bulk counterpart to the per-customer "Reset Portal Password"
button, which staff use to hand a temporary password to someone at the counter.

THE BUG THIS FIXES
------------------
The previous version of this command generated a temp password, stored only its
hash, and told the operator:

    "Existing subscribers must use 'Forgot Password' to receive it."

**There is no Forgot Password feature.** The customer portal has no such view
and no such URL. So running the old command did this for all 2,038 customers:

  * gave each one an unknown random password
  * set must_change_password=True and temp_password_created_at=now
  * delivered the password to nobody

Every subscriber was locked out with no self-service recovery, and the temp
passwords expired after 7 days anyway. It was a one-way trip into a locked
portal.

WHAT IT DOES NOW
----------------
Writes a CSV of `pppoe_username,temp_password` that staff can actually print
and hand out. The passwords are in that file and nowhere else -- as with the
per-customer button, the plaintext is never written to the database.

Treat the CSV as a secret. Delete it once the passwords have been delivered.
"""

import csv

from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Customer
from billing.validators import generate_temp_password


class Command(BaseCommand):
    help = (
        "Bulk-issue portal passwords and write them to a CSV for staff to hand "
        "out. There is NO 'Forgot Password' flow in the portal, so this CSV is "
        "the only way a bulk-reset password reaches a subscriber."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many customers would be affected. Changes nothing.",
        )
        parser.add_argument(
            "--out",
            default="portal_passwords.csv",
            help="CSV file to write (default: portal_passwords.csv in the working dir).",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help=(
                "Required. Acknowledges that the plaintext passwords are written "
                "to a file that must be protected and then destroyed."
            ),
        )

    def handle(self, *args, **options):
        customers = Customer.objects.all().order_by("pppoe_username")
        count = customers.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "[DRY RUN] Would issue a portal password for %d customers "
                    "and write them to %s. Nothing was changed."
                    % (count, options["out"])
                )
            )
            self.stdout.write(
                "  Re-run without --dry-run, and with --confirm, to actually do it."
            )
            return

        if not options["confirm"]:
            self.stderr.write(
                self.style.ERROR(
                    "Refusing to run without --confirm.\n"
                    "This writes %d customers' PLAINTEXT portal passwords to a CSV.\n"
                    "The portal has no 'Forgot Password' flow, so that file is the\n"
                    "only way those passwords reach subscribers. Protect it, deliver\n"
                    "the passwords, then delete it.\n"
                    "Re-run with --dry-run first if you just want the count."
                    % count
                )
            )
            return

        now = timezone.now()
        rows = []
        for customer in customers.iterator():
            temp_pw = generate_temp_password(10)
            customer.set_portal_password(temp_pw)
            customer.must_change_password = True
            customer.temp_password_created_at = now
            customer.save(update_fields=[
                "portal_password_hash",
                "portal_password",
                "must_change_password",
                "temp_password_created_at",
            ])
            rows.append({
                "pppoe_username": customer.pppoe_username or "",
                "temp_password": temp_pw,
                "full_name": customer.full_name or "",
                "phone": customer.phone or "",
            })

        with open(options["out"], "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["pppoe_username", "temp_password", "full_name", "phone"]
            )
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(
            self.style.SUCCESS(
                "Issued portal passwords for %d customers -> %s" % (count, options["out"])
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "This file contains plaintext passwords. Deliver them, then delete it."
            )
        )
        self.stdout.write(
            "Temp passwords expire in 7 days; a subscriber who does not log in "
            "within that window needs a fresh one from the customer page."
        )