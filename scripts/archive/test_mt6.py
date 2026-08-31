import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

device = MikrotikDevice.objects.first()
api = MikrotikAPI(device)
conn = api._get_api()
logs = conn.get_resource('/log').get(topics='pppoe,info')
for l in logs[-100:]:
    if 'lab_test' in l.get('message', ''):
        print(l)
