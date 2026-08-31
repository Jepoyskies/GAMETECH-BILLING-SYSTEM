import os
import django
import sys

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_billing.settings')
django.setup()

from billing.models import Customer, generate_portal_password

def run():
    customers = Customer.objects.filter(portal_password__isnull=True) | Customer.objects.filter(portal_password="")
    updated_count = 0
    for customer in customers:
        customer.portal_password = generate_portal_password()
        customer.save(update_fields=['portal_password'])
        updated_count += 1
    print(f"Successfully generated portal_password for {updated_count} customers.")

if __name__ == '__main__':
    run()
