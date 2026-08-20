import os
import django
import sys
import json
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gametech_core.settings")
django.setup()

from billing.models import Customer
from network_manager.services import MikrotikAPI

# Get the first customer with a Mikrotik device
customer = Customer.objects.exclude(mikrotik_device__isnull=True).first()
if not customer:
    print("No customer with mikrotik device")
    sys.exit()

device = customer.mikrotik_device
print(f"Testing for customer {customer.full_name}, device: {device.name} ({device.ip_address})")

try:
    api = MikrotikAPI(device)
    api_conn = api._get_api()
    print("Connection successful!")
    ping_res = api_conn.get_resource('/').call('ping', {'address': '8.8.8.8', 'count': '1'})
    print("Ping result:", ping_res)
except Exception as e:
    print("Exception during connection:", type(e).__name__, str(e))
