import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from billing.models import SubscriptionPlan

plans = [
    {"name": "20 Mbps Plan", "speed_up": "20M", "speed_down": "20M", "price": 0, "validity_days": 30},
    {"name": "30 Mbps Plan", "speed_up": "30M", "speed_down": "30M", "price": 0, "validity_days": 30},
    {"name": "50 Mbps Plan", "speed_up": "50M", "speed_down": "50M", "price": 0, "validity_days": 30},
    {"name": "75 Mbps Plan", "speed_up": "75M", "speed_down": "75M", "price": 0, "validity_days": 30},
    {"name": "100 Mbps Plan", "speed_up": "100M", "speed_down": "100M", "price": 0, "validity_days": 30},
]

for plan_data in plans:
    plan, created = SubscriptionPlan.objects.get_or_create(
        name=plan_data["name"],
        defaults=plan_data
    )
    if created:
        print(f"Created plan: {plan.name}")
    else:
        print(f"Plan already exists: {plan.name}")
