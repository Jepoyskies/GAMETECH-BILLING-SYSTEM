import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

device = MikrotikDevice.objects.first()
api = MikrotikAPI(device)
conn = api._get_api()
profiles = conn.get_resource('/ppp/profile').get()
print('Profiles:', profiles)
