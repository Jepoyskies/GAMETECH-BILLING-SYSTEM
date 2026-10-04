"""Confirm the staging label and, more importantly, HOW the Sync Manager buckets
a freshly created / imported customer so staff can find it."""
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import Customer, SubscriptionPlan
from network_manager.models import MikrotikDevice

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


dev = MikrotikDevice.objects.get(device_name="Mikrotik A")
plan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()
uname = "e2e_stage2"
Customer.objects.filter(pppoe_username=uname).delete()

print("=" * 76)
print("1. CREATE -> what sync_status ends up as?")
print("=" * 76)
c = Customer.objects.create(
    full_name="TEST Stage2", pppoe_username=uname, pppoe_password="Pw12345",
    status="active", installation_status="installed", plan=plan,
    mikrotik_device=dev, is_test_data=True)
c.refresh_from_db()
print(f"  after create          : {c.sync_status}")

c.sync_status = "Synced"
c.save(update_fields=["sync_status"])
c.refresh_from_db()
print(f"  force to Synced       : {c.sync_status}")

c.full_name = "TEST Stage2 Renamed"
c.save()
c.refresh_from_db()
print(f"  after a router-relevant edit: {c.sync_status}")
check("a router-relevant edit re-stages the customer", c.sync_status == "Pending",
      f"sync_status={c.sync_status}")

c.phone = "09171234567"
c.save()
c.refresh_from_db()
print(f"  after a NON-router edit (phone): {c.sync_status}")
check("a phone-only edit does NOT re-stage (no queue noise)",
      c.sync_status == "Pending", f"sync_status={c.sync_status}")

print()
print("=" * 76)
print("2. HOW DOES THE SYNC MANAGER BUCKET IT?")
print("=" * 76)
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
page = adm.get(f"/devices/devices/{dev.id}/sync/").content.decode()
import re
present = uname in page
check("the customer appears on the Sync Manager page", present)

# Find the section heading that contains it
idx = page.find(uname)
seg = page[max(0, idx - 4000):idx + 600] if idx > -1 else ""
headings = re.findall(r'<(h[1-6]|th|summary)[^>]*>([^<]{3,60})<', seg)
print("  nearby labels:")
for tag, txt in headings[-12:]:
    print(f"     <{tag}> {txt.strip()}")

for probe in ("Push", "missing", "Not on Router", "Needs Review", "Unverified", "Pending"):
    print(f"  page mentions {probe!r}: {probe.lower() in page.lower()}")

print()
print("=" * 76)
print("3. COUNTS THE MANAGER REPORTS")
print("=" * 76)
for label in ("count_missing", "count_orphans", "count_suspicious"):
    m = re.search(rf'{label}[^0-9]{{0,20}}(\d+)', page)
    print(f"  {label:18} = {m.group(1) if m else 'n/a'}")

Customer.objects.filter(pppoe_username=uname).delete()
print()
print("=" * 76)
fails = [r for r in res if not r[0]]
print(f"  {len(res)-len(fails)}/{len(res)} passed")
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print("=" * 76)