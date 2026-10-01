import os
import django
import sys

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_billing.settings')
django.setup()

from billing.models import Customer, generate_portal_password

def run():
    # Hash-only storage: set_portal_password() writes portal_password_hash and
    # blanks the legacy plaintext column. Never write portal_password directly.
    customers = Customer.objects.filter(portal_password_hash__isnull=True) | Customer.objects.filter(portal_password_hash="")
    updated_count = 0
    for customer in customers:
        customer.set_portal_password(generate_portal_password())
        customer.save(update_fields=['portal_password_hash', 'portal_password'])
        updated_count += 1
    print(f"Successfully generated portal_password for {updated_count} customers.")

if __name__ == '__main__':
    run()
