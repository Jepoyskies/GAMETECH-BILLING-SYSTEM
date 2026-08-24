from django.core.management.base import BaseCommand
from billing.models import Customer, generate_portal_password

class Command(BaseCommand):
    help = 'Seed portal_password for existing customers'

    def handle(self, *args, **kwargs):
        customers = Customer.objects.filter(portal_password__isnull=True) | Customer.objects.filter(portal_password="")
        updated_count = 0
        for customer in customers:
            customer.portal_password = generate_portal_password()
            customer.save(update_fields=['portal_password'])
            updated_count += 1
        self.stdout.write(self.style.SUCCESS(f'Successfully generated portal_password for {updated_count} customers.'))
