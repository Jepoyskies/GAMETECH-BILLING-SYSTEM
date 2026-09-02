import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from billing.models import SubscriptionPlan
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI
import time

def sync_all_plans():
    devices = MikrotikDevice.objects.all()
    plans = SubscriptionPlan.objects.all()
    
    print(f"Found {plans.count()} plans and {devices.count()} devices.")
    
    for device in devices:
        print(f"Syncing to {device.device_name} ({device.ip_address})...")
        try:
            api = MikrotikAPI(device)
            success_count = 0
            for plan in plans:
                print(f"  -> Syncing {plan.name} (Up: {plan.speed_up}, Down: {plan.speed_down})")
                success, msg = api.sync_plan_to_mikrotik(
                    plan_name=plan.name,
                    speed_up=plan.speed_up,
                    speed_down=plan.speed_down
                )
                if success:
                    success_count += 1
                else:
                    print(f"     Failed: {msg}")
                time.sleep(0.5)
                
            print(f"Successfully synced {success_count} plans to {device.device_name}")
        except Exception as e:
            print(f"Failed to connect to device {device.device_name}: {e}")

if __name__ == '__main__':
    sync_all_plans()
