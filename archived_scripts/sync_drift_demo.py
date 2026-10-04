"""
Prove plan-drift detection: the scenario the owner described -- "say Juan has a
different plan in the system than in the MikroTik, staff need to SEE that so
they can change it".

Creates a temporary CRM customer whose username matches a REAL secret on
Mikrotik A but with a deliberately different plan, confirms the sync manager
flags it as drift, then removes the temp row.
"""
import re
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import Customer, SubscriptionPlan
from network_manager.models import MikrotikDevice

User = get_user_model()
dev = MikrotikDevice.objects.filter(device_name__icontains="Mikrotik A").first()
target = "Jillian"

have = SubscriptionPlan.objects.filter(name="10Mbps").first()
if not have:
    have = SubscriptionPlan.objects.exclude(name="5Mbps").first()

temp = Customer.objects.filter(pppoe_username=target).first()
created = False
if not temp:
    temp = Customer(
        pppoe_username=target,
        pppoe_password="drift-test-pw",
        full_name="DRIFT TEST Jillian",
        plan=have,
        status="active",
        installation_status="installed",
        mikrotik_device=dev,
        is_test_data=True,
    )
    temp.save()
    created = True
print(f"Temp CRM row for '{target}' created={created}")
print(f"  CRM says the plan/profile should be: {temp.plan.name if temp.plan else None}")

c = Client()
c.force_login(User.objects.get(username="Jep"))
html = c.get(f"/devices/devices/{dev.id}/sync/").content.decode()

print(f"\nSync page HTTP 200, {len(html)} bytes")
print(f"  '{target}' matched on page   : {target in html}")
print(f"  page mentions DRIFT         : {'drift' in html.lower()}")

# Show the row the page renders for this secret.
seg = re.search(rf'(.{{0,600}}{target}.{{0,600}})', html, re.S)
if seg:
    txt = re.sub(r'<[^>]+>', ' ', seg.group(1))
    txt = re.sub(r'\s+', ' ', txt).strip()
    print("\n  row text from the page:")
    print("   ", txt[:420])

if created:
    temp.delete()
    print("\n  temp CRM row removed; database back to previous state")
    print("  remaining customers:", Customer.objects.count())