import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from billing.models import SubscriptionPlan

speeds = {
    "GTipid Fiber 500": (5, 5),
    "GTipid Fiber 750": (10, 10),
    "GTipid Fiber 1000": (20, 20),
    "GTipid Fiber 1300": (30, 30),
    "GTipid Fiber 1500": (50, 50),
    "GIMI Home Fiber 1000": (50, 50),
    "GIMI Home Fiber 1300": (75, 75),
    "GIMI Home Fiber 1500": (100, 100),
    "SME Plan 1999": (50, 100),
    "SME Plan 3999": (100, 200),
    "SME Plan 7999": (200, 400),
    "SME Plan 11999": (300, 600),
    "SME Plan 14999": (400, 800),
    "SME Plan 17999": (500, 1000)
}

for name, (up, down) in speeds.items():
    plan = SubscriptionPlan.objects.filter(name=name).first()
    if plan:
        plan.speed_up = str(up)
        plan.speed_down = str(down)
        plan.save()
        print(f"Updated {name}: {up}/{down}")
    else:
        print(f"Plan not found: {name}")
