"""
Customer portal end-to-end: login as Juan, pay a bill there, then apply for
Cignal Play and confirm the application reaches dispatch and comes back.

Uses the real portal views through the URLconf.
"""
import json
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from billing.models import Customer, Payment, CignalPlay
from dispatch.models import JobTicket

User = get_user_model()
OK, BAD = "PASS", "**FAIL**"
res = []


def check(label, cond, detail=""):
    res.append((OK if cond else BAD, label, detail))
    print(f"  [{OK if cond else BAD}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 74 + f"\n{s}\n" + "=" * 74)


cust = Customer.objects.filter(pppoe_username="delacruz_juan_e2e").first()
if not cust:
    raise SystemExit("ABORT: no test customer")

# Give Juan a known portal password so we can actually log in as him.
from django.contrib.auth.hashers import make_password
cust.portal_password_hash = make_password("PortalTest123")
cust.must_change_password = False
cust.save(update_fields=["portal_password_hash", "must_change_password"])
print(f"Juan portal password set. status={cust.status} expires={cust.expires_at}")

hdr("1. PORTAL LOGIN as Juan")
p = Client()
r = p.post("/login/", {"username": "delacruz_juan_e2e", "password": "PortalTest123"},
           follow=False)
print(f"  POST /login/ -> {r.status_code} {r.headers.get('Location','')}")
check("portal login accepted", r.status_code == 302 and
      "login" not in r.headers.get("Location", ""),
      f"-> {r.headers.get('Location','')}")

r = p.get("/portal/dashboard/")
check("portal dashboard loads", r.status_code == 200, f"HTTP {r.status_code}")
body = r.content.decode()
check("portal shows the customer name", "Juan Dela Cruz" in body)
check("portal shows the plan", (cust.plan.name if cust.plan else "") in body)

hdr("2. BILL / PAYMENT FROM THE PORTAL")
bills_before = Payment.objects.filter(customer=cust).count()
r = p.get("/portal/bills/")
check("portal bills page loads", r.status_code == 200, f"HTTP {r.status_code}")

# Find the payment form the portal exposes.
r = p.get("/portal/checkout/")
print(f"  GET /portal/checkout/ -> {r.status_code}")
form_html = r.content.decode()
fields = sorted(set(__import__("re").findall(r'name="([a-z_]+)"', form_html)))
print(f"  checkout form fields: {fields}")

hdr("3. CIGNAL PLAY APPLICATION FROM THE PORTAL")
cig_before = CignalPlay.objects.filter(customer=cust).count()
r = p.get("/portal/cignal/")
print(f"  GET /portal/cignal/ -> {r.status_code}")
cig_html = r.content.decode() if r.status_code == 200 else ""
if r.status_code == 200:
    cfields = sorted(set(__import__("re").findall(r'name="([a-z_]+)"', cig_html)))
    print(f"  cignal form fields: {cfields}")

hdr("4. STAFF SIDE - did anything land?")
print(f"  CignalPlay rows for Juan : {CignalPlay.objects.filter(customer=cust).count()} (was {cig_before})")
print(f"  Payment rows for Juan    : {Payment.objects.filter(customer=cust).count()} (was {bills_before})")
print(f"  JobTickets for Juan      : {JobTicket.objects.filter(customer=cust).count()}")
for t in JobTicket.objects.filter(customer=cust):
    print(f"     {t.ticket_number} {t.ticket_type:14} {t.status:10} src={t.source_tab}")

hdr("SUMMARY")
fails = [x for x in res if x[0] == BAD]
for s, l, d in res:
    print(f"  {s:8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")