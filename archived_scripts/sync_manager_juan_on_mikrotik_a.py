"""
Reassign the test customer to MikroTik A and re-run the sync manager, so the
CRM-vs-router reconciliation the owner actually cares about is demonstrated:
Juan exists in the CRM, has NO secret on the router, so staff can see him in
the "missing on router" queue and push him.
"""
import re
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import Customer
from network_manager.models import MikrotikDevice

User = get_user_model()
dev = MikrotikDevice.objects.filter(device_name__icontains="Mikrotik A").first()
cust = Customer.objects.filter(pppoe_username="delacruz_juan_e2e").first()

print("BEFORE: Juan device =", cust.mikrotik_device, "| sync_status =", cust.sync_status)
cust.mikrotik_device = dev
cust.save(update_fields=["mikrotik_device"])
cust.refresh_from_db()
print("AFTER : Juan device =", cust.mikrotik_device, "| sync_status =", cust.sync_status)

c = Client()
c.force_login(User.objects.get(username="Jep"))
url = f"/devices/devices/{dev.id}/sync/"
html = c.get(url).content.decode()
print(f"\nSync manager {url} -> HTTP 200, {len(html)} bytes")

print("\nDoes the page now know Juan?")
for probe in ["delacruz_juan_e2e", "Juan Dela Cruz"]:
    print(f"   '{probe}': {probe in html}")

print("\nCounts rendered on the page:")
for label in ["Synced", "Missing", "Orphan", "Suspicious", "Review", "Drift"]:
    # find the stat tile: a number followed shortly by the label
    hits = re.findall(rf'(\d+)\s*</[^>]+>\s*(?:<[^>]+>\s*)*?{label}', html, re.I)
    print(f"   {label:12} {hits[:3]}")

print("\n--- raw context around the sync stat tiles ---")
for m in re.finditer(r'(Missing[^<]{0,30})', html, re.I):
    seg = html[max(0, m.start() - 300):m.start() + 60]
    nums = re.findall(r'>\s*(\d+)\s*<', seg)
    if nums:
        print(f"   ...{nums[-2:]} {m.group(1).strip()}")

print("\n--- MikroTik A secrets the page is showing ---")
for n in ["delacruz_juan", "jane_pppoe", "john_pppoe", "Jillian"]:
    print(f"   {n:18} in page: {n in html}")

print("\n--- what the CRM says Juan should be ---")
print("   pppoe_username :", cust.pppoe_username)
print("   pppoe_password :", cust.pppoe_password)
print("   plan (profile) :", cust.plan.name if cust.plan else None)
print("   status         :", cust.status, "| expires:", cust.expires_at)