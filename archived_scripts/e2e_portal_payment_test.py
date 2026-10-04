"""Customer portal: pay a bill online, apply an add-on, raise a ticket.
Cignal Play has NO portal endpoint - confirmed against customer_portal/urls.py.
"""
import json
from django.test import Client
from django.contrib.auth.hashers import make_password
from billing.models import Customer, Payment, AddOnRequest
from dispatch.models import JobTicket, DispatchRecord

OK, BAD = "PASS", "**FAIL**"
res = []


def check(label, cond, detail=""):
    res.append((OK if cond else BAD, label, detail))
    print(f"  [{OK if cond else BAD}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 74 + f"\n{s}\n" + "=" * 74)


cust = Customer.objects.filter(pppoe_username="delacruz_juan_e2e").first()
cust.portal_password_hash = make_password("PortalTest123")
cust.must_change_password = False
cust.save(update_fields=["portal_password_hash", "must_change_password"])

p = Client()
p.post("/login/", {"username": "delacruz_juan_e2e", "password": "PortalTest123"})

hdr("1. PORTAL PAGES")
for url in ["/portal/dashboard/", "/portal/checkout/", "/portal/statement/",
            "/portal/tickets/", "/portal/cignal/"]:
    r = p.get(url)
    mark = "OK " if r.status_code in (200, 302) else "GONE"
    print(f"  [{mark}] {url:28} -> {r.status_code}")

hdr("2. PAY A BILL IN THE PORTAL")
exp_before = cust.expires_at
pays_before = Payment.objects.filter(customer=cust).count()
print(f"  before: expires_at={exp_before} payments={pays_before}")

r = p.post("/portal/process-mock-payment/", {
    "amount": str(cust.plan.price if cust.plan else 500),
    "payment_method": "online",
    "period": "1",
    "plan_id": str(cust.plan_id),
}, follow=False, headers={"x-requested-with": "XMLHttpRequest"})
print(f"  POST /portal/process-mock-payment/ -> {r.status_code}")
print(f"  body: {r.content.decode()[:260]}")

cust.refresh_from_db()
pays_after = Payment.objects.filter(customer=cust).count()
print(f"\n  after : expires_at={cust.expires_at} payments={pays_after} status={cust.status}")
check("portal payment created a Payment row", pays_after > pays_before,
      f"{pays_before} -> {pays_after}")
check("due date moved forward",
      cust.expires_at is not None and exp_before is not None and cust.expires_at > exp_before,
      f"{exp_before} -> {cust.expires_at}")

hdr("3. ADD-ON APPLICATION FROM THE PORTAL")
add_before = AddOnRequest.objects.filter(customer=cust).count()
r = p.post("/portal/api/apply-addon/",
           data=json.dumps({"addon_id": 1, "notes": "portal test"}),
           content_type="application/json",
           headers={"x-requested-with": "XMLHttpRequest"})
print(f"  POST /portal/api/apply-addon/ -> {r.status_code}")
print(f"  body: {r.content.decode()[:220]}")
add_after = AddOnRequest.objects.filter(customer=cust).count()
print(f"  AddOnRequest rows: {add_before} -> {add_after}")
check("add-on request created", add_after > add_before)

hdr("4. SUPPORT TICKET FROM THE PORTAL")
t_before = DispatchRecord.objects.filter(customer=cust).count()
j_before = JobTicket.objects.filter(customer=cust).count()
r = p.post("/portal/submit-ticket/", {
    "subject": "Line is down",
    "description": "No internet since this morning, red light on the ONT.",
    "category": "technical",
}, follow=False)
print(f"  POST /portal/submit-ticket/ -> {r.status_code} {r.headers.get('Location','')}")
print(f"  DispatchRecord: {t_before} -> {DispatchRecord.objects.filter(customer=cust).count()}")
print(f"  JobTicket     : {j_before} -> {JobTicket.objects.filter(customer=cust).count()}")
check("portal ticket reached dispatch",
      (DispatchRecord.objects.filter(customer=cust).count() > t_before
       or JobTicket.objects.filter(customer=cust).count() > j_before))

hdr("SUMMARY")
fails = [x for x in res if x[0] == BAD]
for s, l, d in res:
    print(f"  {s:8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")