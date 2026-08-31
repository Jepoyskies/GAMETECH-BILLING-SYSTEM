import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from billing.models import Customer
c = Customer.objects.get(pppoe_username='lab_test')
print('Status:', c.status, 'Plan:', c.plan)
