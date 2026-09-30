"""
Bulk-reset portal passwords for all customers.
Generates a new temp password for each, storing both hash and staff-visible plaintext.
"""

from django.core.management.base import BaseCommand
from billing.models import Customer
from billing.validators import generate_temp_password
from django.utils import timezone


class Command(BaseCommand):
    help = "Reset portal passwords for all customers (populates plaintext field for staff visibility)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many customers would be affected without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        customers = Customer.objects.all()
        count = customers.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would reset passwords for {count} customers."))
            return

        updated = 0
        for customer in customers:
            temp_pw = generate_temp_password(10)
            customer.set_portal_password(temp_pw)
            customer.must_change_password = True
            customer.temp_password_created_at = timezone.now()
            customer.save(update_fields=[
                "portal_password_hash",
                "portal_password",
                "portal_password_plaintext",
                "must_change_password",
                "temp_password_created_at",
            ])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Reset portal passwords for {updated} customers."))
