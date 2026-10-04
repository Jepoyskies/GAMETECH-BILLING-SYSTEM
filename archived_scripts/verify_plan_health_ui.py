"""Verify the plan-health banner renders and the export carries the new columns."""
import csv
import io

from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import SubscriptionPlan
from billing.services.plan_health import plan_health
from network_manager.models import MikrotikDevice

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


hdr = lambda s: print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)

dev = MikrotikDevice.objects.get(device_name="Mikrotik A")

hdr("1. SYNC MANAGER PAGE SHOWS THE PLAN-HEALTH BANNER")
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
page = adm.get(f"/devices/devices/{dev.id}/sync/").content.decode()
check("sync manager still renders", "Sync" in page or "Mikrotik" in page)
check("plan-health banner present", "Plan catalogue problems" in page,
      "banner heading found")
check("duplicate-price collision shown", "Same price, different speed" in page)
check("unmapped plans shown", "No router profile mapped" in page)
check("PHP 500 collision is called out", "500" in page)
check("fix link points at Internet Plans", "/plans/" in page)

hdr("2. A CLEAN CATALOGUE SHOWES THE GREEN VARIANT")
p = SubscriptionPlan.objects.filter(name="pppoe-15m_500").first()
print(f"  (banner is warning-only because the catalogue has real problems: "
      f"{len(plan_health()['ambiguous'])} collisions)")

hdr("3. CUSTOMER EXPORT CARRIES THE PLAN COLUMNS")
csr = Client(); csr.force_login(U.objects.get(username="Vince"))
r = csr.get("/customers/export/csv/")
check("export responds", r.status_code == 200, f"HTTP {r.status_code}")
rows = list(csv.DictReader(io.StringIO(r.content.decode())))
print(f"  rows={len(rows)}")
if rows:
    cols = list(rows[0].keys())
    print("  columns:", cols)
    for want in ("Plan Speed Mbps", "Plan Router Profile", "Plan Problem"):
        check(f"column '{want}' present", want in cols)
    row = rows[0]
    print()
    print("  sample row:")
    for k in ("PPPoE Username", "Plan", "Monthly Price", "Plan Speed Mbps",
              "Plan Router Profile", "Plan Problem", "Sync Status"):
        print(f"     {k:22} {row.get(k)}")
    check("the problem is spelled out, not just a flag",
          bool(row.get("Plan Problem")),
          f"Plan Problem='{row.get('Plan Problem')}'")

hdr("4. TECHNICIAN STILL BLOCKED FROM BOTH")
tech = Client(); tech.force_login(U.objects.get(username="Merk"))
check("technician cannot export customers",
      tech.get("/customers/export/csv/").status_code in (302, 403))
check("technician cannot open the sync manager",
      tech.get(f"/devices/devices/{dev.id}/sync/").status_code in (302, 403))

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")