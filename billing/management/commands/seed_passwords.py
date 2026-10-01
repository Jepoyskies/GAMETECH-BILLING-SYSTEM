from django.core.management.base import BaseCommand
from billing.models import Customer, generate_portal_password


class Command(BaseCommand):
    help = "Seed portal_password for existing customers"

    def handle(self, *args, **kwargs):
        # Hash-only storage: set_portal_password() writes portal_password_hash and
        # blanks the legacy plaintext column. Never write portal_password directly.
        customers = Customer.objects.filter(
            portal_password_hash__isnull=True
        ) | Customer.objects.filter(portal_password_hash="")
        updated_count = 0
        for customer in customers:
            customer.set_portal_password(generate_portal_password())
            customer.save(update_fields=["portal_password_hash", "portal_password"])
            updated_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully generated portal_password for {updated_count} customers."
            )
        )
