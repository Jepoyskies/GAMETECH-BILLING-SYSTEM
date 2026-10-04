"""
Drive the REAL sync_manager view for MikroTik A and show its categorisation.
Read-only: the view only reads the router. Proves whether the sync manager
actually detects our test customer and reports plan drift.
"""
import re
from django.test import Client
from django.contrib.auth import get_user_model
from network_manager.models import MikrotikDevice

User = get_user_model()

dev = MikrotikDevice.objects.filter(device_name__icontains="Mikrotik A").first()
print(f"Device: {dev.device_name} (id={dev.id}) ip={dev.ip_address}")

c = Client()
c.force_login(User.objects.get(username="Jep"))
# network_manager.urls is mounted under "devices/", so the real path is
# /devices/devices/<id>/sync/  -- not /devices/<id>/sync/
url = f"/devices/devices/{dev.id}/sync/"
r = c.get(url)
print(f"GET {url} -> HTTP {r.status_code}")
html = r.content.decode()

# Pull the counts the view renders into context-driven badges/headings.
for label in ["Synced", "Missing on Router", "Clean Orphan", "Suspicious",
              "Needs Review", "Drift", "Connected but Unpaid"]:
    for m in re.finditer(rf'>\s*{label}\s*<', html, re.I):
        seg = html[max(0, m.start() - 220):m.start() + 90]
        nums = re.findall(r'>\s*(\d+)\s*<', seg)
        print(f"   {label:22} -> nearby counts {nums[-3:] if nums else 'n/a'}")

print("\n--- usernames the page mentions ---")
names = set(re.findall(r'\b([a-z]+_[a-z0-9_]+|[A-Z][a-z]+)\b', html))
for n in sorted(names):
    if n in ("jane_pppoe", "john_pppoe", "Jillian", "delacruz_juan", "delacruz_juan_e2e"):
        print("   FOUND:", n)

print("\n--- our test customer references ---")
for probe in ["delacruz_juan_e2e", "Juan Dela Cruz", "e2e"]:
    print(f"   '{probe}' present in page: {probe in html}")

print("\n--- keyword presence ---")
for kw in ["orphan", "missing", "drift", "Unpaid", "disabled", "Blocked", "read_only"]:
    print(f"   {kw:12}: {html.lower().count(kw.lower())} occurrences")