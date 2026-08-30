import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from billing.models import SubscriptionPlan

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
