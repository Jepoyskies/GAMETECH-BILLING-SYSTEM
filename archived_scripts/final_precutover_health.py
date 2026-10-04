"""
FINAL PRE-CUTOVER HEALTH CHECK.

Answers one question: are we greenlighted, and if not, what exactly is left.
Read-only. Touches nothing.
"""
import csv
import io

from django.contrib.auth import get_user_model
from django.test import Client

from billing.models import Customer, Payment, SubscriptionPlan, Prospect
from billing.services.plan_health import plan_health, health_summary_line
from network_manager.models import MikrotikDevice

U = get_user_model()
res = []


def check(label, ok, detail=""):
    res.append((bool(ok), label, detail))
    print(f"  [{'PASS' if ok else '**FAIL**'}] {label} {detail}")


hdr = lambda s: print("\n" + "=" * 78 + f"\n{s}\n" + "=" * 78)

hdr("1. DATA STATE -- ready for a clean import tomorrow?")
check("exactly 1 demo customer", Customer.objects.count() == 1,
      f"count={Customer.objects.count()}")
check("2 payments", Payment.objects.count() == 2,
      f"count={Payment.objects.count()}")
check("no prospects", Prospect.objects.count() == 0,
      f"count={Prospect.objects.count()}")
check("plans preserved", SubscriptionPlan.objects.count() >= 30,
      f"count={SubscriptionPlan.objects.count()}")

hdr("2. ALL SIX PERSONAS LOG IN AND LAND WHERE THEY SHOULD")
EXPECT = {
    "Jep": ("/", "admin"),
    "Jill": ("/", "admin"),
    "Admin": ("/", "admin"),
    "Vince": ("/", "csr"),
    "Martin": ("/", "agent"),
    "Merk": ("/", "technician"),
}
for uname, (_, role) in EXPECT.items():
    u = U.objects.filter(username=uname).first()
    if not u:
        check(f"{uname} exists", False)
        continue
    c = Client()
    ok_login = c.login(username=uname, password={
        "Jep": "1234", "Jill": "1234", "Admin": "1234",
        "Vince": "csr-12345678", "Martin": "agent-12345678",
        "Merk": "tech-12345678",
    }[uname])
    check(f"{uname} ({role}) logs in", ok_login)
    r = c.get("/", follow=True)
    check(f"{uname} reaches a 200 landing page", r.status_code == 200,
          f"HTTP {r.status_code}")

hdr("3. BUSINESS FLOWS STILL REACHABLE (no 500s)")
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
csr = Client(); csr.force_login(U.objects.get(username="Vince"))
PAGES = [
    ("customers list",       "/customers/",                     adm),
    ("customer export",      "/customers/export/csv/",          csr),
    ("payments",             "/payments/",                      csr),
    ("plans",                "/plans/",                         adm),
    ("add plan",             "/plans/add/",                     adm),
    ("subscriptions",        "/subscriptions/",                 adm),
    ("dispatch",             "/dispatch/",                      adm),
    ("invoices",             "/invoices/",                      adm),
    ("agents",               "/agents/",                        adm),
    ("prospects",            "/prospects/",                     adm),
    ("network devices",      "/devices/devices/",               adm),
    ("import review",        "/settings/import/",               adm),
    ("analytics",            "/analytics/",                     adm),
    ("role editor",          "/settings/roles/",               adm),
]
for label, url, cli in PAGES:
    r = cli.get(url, follow=True)
    check(f"{label:20} {url:26}", r.status_code == 200, f"HTTP {r.status_code}")

hdr("4. RENDERED HTML IS REAL, NOT AN ERROR PAGE")
for label, url in [("customers", "/customers/"), ("plans", "/plans/")]:
    html = adm.get(url).content.decode()
    check(f"{label} page has content", len(html) > 3000, f"{len(html)} bytes")
    check(f"{label} page has no traceback", "Traceback" not in html)

hdr("5. EXPORT STILL CARRIES THE PLAN PROBLEM COLUMNS")
r = csr.get("/customers/export/csv/")
rows = list(csv.DictReader(io.StringIO(r.content.decode())))
cols = list(rows[0].keys()) if rows else []
for want in ("Plan Speed Mbps", "Plan Router Profile", "Plan Problem"):
    check(f"export column '{want}'", want in cols)

hdr("6. PLAN CATALOGUE -- the one thing still needing your decision")
h = plan_health()
print(f"  {health_summary_line()}")
print(f"  mapped to a router profile : {h['plans_with_profile']}/{h['total_plans']}")
print()
for a in h["ambiguous"]:
    print(f"  COLLISION  PHP {a['price']:>9,.0f}  "
          f"{' / '.join(a['plans'])}  ({a['speeds']})")
print()
inuse = {c.plan.name for c in Customer.objects.filter(plan__isnull=False)}
unmapped_in_use = inuse & {u["name"] for u in h["unmapped"]}
print(f"  plans in use today with NO profile: {sorted(unmapped_in_use) or 'none'}")
print()
print("  >> tomorrow these matter more, because the real import will put")
print("     2,041 customers onto whatever plans the export names.")
check("no duplicate-price collision is unresolved",
      len(h["ambiguous"]) == 0, f"{len(h['ambiguous'])} remain")
check("every in-use plan has a router profile",
      not unmapped_in_use, f"{len(unmapped_in_use)} unmapped in use")

hdr("7. ROUTERS")
for d in MikrotikDevice.objects.all():
    print(f"  {d.device_name:32} {d.ip_address:16} enabled={d.is_enabled}")

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    if not ok:
        print(f"  **FAIL** {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed, {len(fails)} failing")
print("=" * 78)
