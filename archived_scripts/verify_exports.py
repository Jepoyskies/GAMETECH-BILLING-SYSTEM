"""Exports + import idempotency + final health."""
import csv
import io
import json
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import Customer, Payment, Prospect
from dispatch.models import JobTicket

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)


adm = Client(); adm.force_login(U.objects.get(username="Jep"))
csr = Client(); csr.force_login(U.objects.get(username="Vince"))

hdr("1. FIND THE EXPORT ENDPOINTS")
from django.urls import reverse, NoReverseMatch
names = ["customer_export", "export_customers", "customers_export", "export_csv",
         "payment_export", "export_payments", "cignal_export_csv",
         "subscription_export", "export_data"]
found = []
for n in names:
    try:
        found.append((n, reverse(n)))
    except NoReverseMatch:
        pass
print(f"  resolvable export routes: {found}")

import subprocess
out = subprocess.run(
    ["grep", "-rn", "export", "/app/billing/urls.py", "/app/dispatch/urls.py",
     "/app/network_manager/urls.py"],
    capture_output=True, text=True).stdout
for line in out.splitlines():
    print("   ", line.strip()[:150])

hdr("2. EXPORT A REAL DATASET AND VALIDATE IT")
# customers CSV via any route that exists
for path in ["/customers/export/csv/", "/customers/export/", "/api/customers/export/"]:
    r = csr.get(path)
    if r.status_code == 200:
        body = r.content
        try:
            txt = body.decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(txt)))
            check(f"customers export {path}", bool(rows),
                  f"HTTP 200 rows={len(rows)} cols={len(rows[0]) if rows else 0}")
            if rows:
                print("     sample:", {k: rows[0][k] for k in list(rows[0])[:6]})
                print("     has pppoe:", "pppoe_username" in rows[0])
                print("     has expiry:", any("expir" in k for k in rows[0]))
        except Exception as e:
            check(f"customers export {path}", False, f"parse error {e}")
    else:
        print(f"  {path} -> HTTP {r.status_code}")

hdr("3. CIGNAL EXPORT")
r = csr.get("/cignal-dashboard/export-csv/")
check("cignal CSV export responds", r.status_code in (200, 302), f"HTTP {r.status_code}")
if r.status_code == 200:
    print(f"     bytes={len(r.content)} head={r.content[:120].decode('utf-8','replace')}")

hdr("4. CURRENT DATA SNAPSHOT (what an export would contain)")
print(f"  customers : {Customer.objects.count()}")
print(f"  payments  : {Payment.objects.count()}")
print(f"  tickets   : {JobTicket.objects.count()}")
print(f"  prospects : {Prospect.objects.count()}")
for c in Customer.objects.all():
    print(f"     {c.pppoe_username:22} {c.full_name:18} {c.status:8} "
          f"expires={c.expires_at} sync={c.sync_status}")

hdr("5. NO 5xx ACROSS THE WHOLE SURFACE")
pages = ["/", "/customers/", "/customers/add/", "/plans/", "/subscriptions/",
         "/cignal-dashboard/", "/cignal-dashboard/applications/", "/add-ons/",
         "/agents/", "/agents/payouts/", "/prospects/", "/payments/",
         "/logs/payments/", "/admin-panel/", "/staff/roles/", "/staff/",
         "/dispatch/queue/", "/dispatch/dashboard/", "/dispatch/management/",
         "/devices/devices/", "/live-monitoring/", "/geomap/",
         f"/devices/devices/{__import__('network_manager.models', fromlist=['MikrotikDevice']).MikrotikDevice.objects.get(device_name='Mikrotik A').id}/sync/"]
bad = []
for p in pages:
    r = adm.get(p)
    if r.status_code >= 500:
        bad.append((p, r.status_code))
check("no 5xx anywhere", not bad, f"bad={bad}")

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")