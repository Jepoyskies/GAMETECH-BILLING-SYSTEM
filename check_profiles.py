import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from network_manager.services import MikrotikAPI
from network_manager.models import MikrotikDevice

device = MikrotikDevice.objects.first()
print(f"Connecting to {device.device_name}...")
api = MikrotikAPI(device)
try:
    router_api = api._get_api()
    profiles = router_api.get_resource('/ppp/profile').get()
    print("Available Profiles on MikroTik:")
    for p in profiles:
        print(f" - '{p.get('name')}'")
except Exception as e:
    print(f"Error: {e}")
