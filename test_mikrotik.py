import os
import django

# Setup Django environment so we can use our models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

def test_router():
    print("🔍 Searching for MikroTik devices in database...")
    device = MikrotikDevice.objects.first()
    
    if not device:
        print("❌ No MikroTik device found in the database. Please add one in the Django Admin first!")
        return

    print(f"📡 Connecting to {device.device_name} at {device.ip_address}...")
    
    api = MikrotikAPI(device)
    users = api.get_active_pppoe_users()
    
    print("\n✅ Successfully connected! Here are the active PPPoE users:")
    for user in users:
        print(f" - Username: {user.get('name', 'Unknown')} | Uptime: {user.get('uptime', 'N/A')}")
        
    print("\n🎉 The MikroTik integration works perfectly!")

if __name__ == '__main__':
    test_router()
