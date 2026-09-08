import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()
from network_manager.services import MikrotikAPI
from network_manager.models import MikrotikDevice

device = MikrotikDevice.objects.get(id=2)
api = MikrotikAPI(device)
secrets = api._get_api().get_resource('/ppp/secret')
all_secrets = secrets.get()
print("Found", len(all_secrets), "secrets")
if all_secrets:
    test_secret = all_secrets[-1]
    print("Secret keys:", test_secret.keys())
    print("Secret:", test_secret)
