import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from network_manager.models import MikrotikDevice
print([(d.device_name, d.ip_address) for d in MikrotikDevice.objects.all()])
