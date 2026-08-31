import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from billing.models import Customer
print(Customer.objects.get(pppoe_username='lab_test').mac_address)
