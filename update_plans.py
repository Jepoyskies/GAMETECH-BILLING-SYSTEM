import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from billing.models import SubscriptionPlan

def update_plans():
    # 1. Delete all existing plans
    print("Deleting existing subscription plans...")
    SubscriptionPlan.objects.all().delete()
    
    # 2. Define the new official plans
    plans_data = [
        # GTipid Fiber
        {"name": "GTipid Fiber 1000", "speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 1000},
        {"name": "GTipid Fiber 1300", "speed_up": "30 Mbps", "speed_down": "30 Mbps", "price": 1300},
        {"name": "GTipid Fiber 1500", "speed_up": "50 Mbps", "speed_down": "50 Mbps", "price": 1500},
        
        # Gimi Home Fiber
        {"name": "GIMI Home Fiber 1000", "speed_up": "50 Mbps", "speed_down": "50 Mbps", "price": 1000},
        {"name": "GIMI Home Fiber 1300", "speed_up": "75 Mbps", "speed_down": "75 Mbps", "price": 1300},
        {"name": "GIMI Home Fiber 1500", "speed_up": "100 Mbps", "speed_down": "100 Mbps", "price": 1500},
        
        # Business Plans (SME)
        {"name": "SME Plan 1999", "speed_up": "100 Mbps", "speed_down": "50 Mbps", "price": 1999},
        {"name": "SME Plan 3999", "speed_up": "200 Mbps", "speed_down": "100 Mbps", "price": 3999},
        {"name": "SME Plan 7999", "speed_up": "400 Mbps", "speed_down": "200 Mbps", "price": 7999},
        {"name": "SME Plan 11999", "speed_up": "600 Mbps", "speed_down": "300 Mbps", "price": 11999},
        {"name": "SME Plan 14999", "speed_up": "800 Mbps", "speed_down": "400 Mbps", "price": 14999},
        {"name": "SME Plan 17999", "speed_up": "1 Gbps", "speed_down": "500 Mbps", "price": 17999},
        
        # Enterprise Plan
        {"name": "Enterprise Plan", "speed_up": "Custom", "speed_down": "Custom", "price": 0},
    ]
    
    print(f"Creating {len(plans_data)} new official plans...")
    for data in plans_data:
        plan = SubscriptionPlan.objects.create(
            name=data["name"],
            speed_up=data["speed_up"],
            speed_down=data["speed_down"],
            price=data["price"],
            validity_days=30,
            description="Official Plan from gametechunlifiberph.com"
        )
        print(f"Created: {plan.name} at P{plan.price}")
        
    print("Plan update complete.")

if __name__ == '__main__':
    update_plans()

    # Legacy Plans
    SubscriptionPlan.objects.get_or_create(
        name='5Mbps', 
        defaults={'speed_up': '5 Mbps', 'speed_down': '5 Mbps', 'price': 500, 'validity_days': 30, 'description': 'Legacy Plan'}
    )
    SubscriptionPlan.objects.get_or_create(
        name='10Mbps', 
        defaults={'speed_up': '10 Mbps', 'speed_down': '10 Mbps', 'price': 750, 'validity_days': 30, 'description': 'Legacy Plan'}
    )
    print('Legacy plans added.')
