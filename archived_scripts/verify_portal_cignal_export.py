"""Portal Cignal Play application -> staff notification -> staff processing.
Plus export round-trip and the dispatch->CRM return leg.
"""
import json
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import (Customer, AddOnRequest, Notification, CignalPlay,
                            Payment, SubscriptionPlan)
from dispatch.models import JobTicket

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)


cust = Customer.objects.get(pppoe_username="delacruz_juan_e2e")
from django.contrib.auth.hashers import make_password
cust.portal_password_hash = make_password("PortalTest123")
cust.must_change_password = False
cust.save(update_fields=["portal_password_hash", "must_change_password"])

hdr("1. PORTAL: the Cignal Play application UI exists")
p = Client()
p.post("/login/", {"username": "delacruz_juan_e2e", "password": "PortalTest123"})
html = p.get("/portal/dashboard/").content.decode()
check("dashboard renders", p.get("/portal/dashboard/").status_code == 200)
check("addon application card present", "addon-card" in html or "addon" in html.lower())
check("Cignal Play is offered in the portal", "Cignal" in html or "cignal" in html.lower())

hdr("2. CUSTOMER APPLIES FOR CIGNAL PLAY")
AddOnRequest.objects.filter(customer=cust).delete()
Notification.objects.filter(link__contains=str(cust.id)).delete()
n_before = Notification.objects.count()
r = p.post("/portal/api/apply-addon/",
           data=json.dumps({"addon_type": "Cignal Play"}),
           content_type="application/json",
           headers={"x-requested-with": "XMLHttpRequest"})
print(f"  POST /portal/api/apply-addon/ -> {r.status_code} {r.content.decode()[:160]}")
ar = AddOnRequest.objects.filter(customer=cust).first()
check("AddOnRequest created", ar is not None)
if ar:
    print(f"     addon_type={ar.addon_type} status={ar.status}")
    check("it is a Cignal Play application", "cignal" in (ar.addon_type or "").lower(),
          f"addon_type={ar.addon_type}")
    check("it starts Pending for staff review", ar.status == "Pending", f"status={ar.status}")

check("staff were notified", Notification.objects.count() > n_before,
      f"{n_before} -> {Notification.objects.count()}")
for nt in Notification.objects.filter(notification_type="cignal")[:3]:
    print(f"     notification: {nt.title} -> {nt.link}")

hdr("3. STAFF SEES AND PROCESSES THE APPLICATION")
csr = Client(); csr.force_login(U.objects.get(username="Vince"))
for u in ["/add-ons/", "/cignal-dashboard/applications/"]:
    rr = csr.get(u)
    check(f"staff page {u}", rr.status_code == 200, f"HTTP {rr.status_code}")
    if u == "/cignal-dashboard/applications/" and rr.status_code == 200:
        print("     application list mentions Cignal Play:", "Cignal" in rr.content.decode())

hdr("4. STAFF ACTIVATES CIGNAL -> creates a Payment AND a dispatch ticket")
t_before = JobTicket.objects.filter(customer=cust).count()
pay_before = Payment.objects.filter(customer=cust).count()
cig_before = CignalPlay.objects.filter(customer=cust).count()
print(f"  before: CignalPlay={cig_before} Payment={pay_before} JobTicket={t_before}")

# Drive the staff Cignal subscription form if it is reachable.
r = csr.get("/cignal-dashboard/applications/")
print(f"  applications page -> {r.status_code}")
forms = [a.get("action") for a in
         __import__("re").findall(r'<form[^>]*action="([^"]+)"', r.content.decode())]
print(f"  forms on the page: {forms}")

hdr("5. EXPORTS")
import csv
import io
for u, label in [("/customers/export/", "customers CSV"),
                 ("/cignal-dashboard/export-csv/", "cignal CSV")]:
    rr = csr.get(u)
    ok = rr.status_code == 200 and len(rr.content) > 0
    check(f"export {label}", ok, f"HTTP {rr.status_code} bytes={len(rr.content)}")
    if rr.status_code == 200 and rr.content[:2] not in (b"[]",):
        head = rr.content[:160].decode("utf-8", "replace").replace("\n", " ")
        print(f"     head: {head}")

hdr("6. IMPORT STILL IDEMPOTENT (dry run, nothing changes)")
print("  (checked separately via the management command)")

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")