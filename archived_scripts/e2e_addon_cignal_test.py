"""Add-on with the correct field, then the STAFF-side Cignal Play application
and its dispatch bridge (billing/views/services.py creates a CIGNAL JobTicket).
"""
import json
from django.test import Client
from django.contrib.auth.hashers import make_password
from billing.models import Customer, AddOnRequest, CignalPlay
from dispatch.models import JobTicket

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

hdr("1. ADD-ON APPLICATION (correct field: addon_type)")
p = Client()
p.post("/login/", {"username": "delacruz_juan_e2e", "password": "PortalTest123"})
before = AddOnRequest.objects.filter(customer=cust).count()
r = p.post("/portal/api/apply-addon/",
           data=json.dumps({"addon_type": "Cignal Play"}),
           content_type="application/json",
           headers={"x-requested-with": "XMLHttpRequest"})
after = AddOnRequest.objects.filter(customer=cust).count()
print(f"  HTTP {r.status_code} -> {r.content.decode()[:200]}")
print(f"  AddOnRequest: {before} -> {after}")
check("add-on request created", after > before)

hdr("2. STAFF CIGNAL DASHBOARD")
c = Client()
c.force_login(__import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.get(username="Vince"))
for url in ["/cignal-dashboard/", "/cignal-dashboard/applications/", "/cignal-dashboard/logs/"]:
    r = c.get(url)
    print(f"  {url:38} -> {r.status_code}")

hdr("3. CIGNAL SUBSCRIPTION -> DISPATCH BRIDGE")
print("  The bridge lives in billing/views/services.py: a CignalPlay created by")
print("  staff auto-creates a JobTicket(ticket_type='CIGNAL').")
cig_before = CignalPlay.objects.filter(customer=cust).count()
t_before = JobTicket.objects.filter(customer=cust).count()
print(f"  before: CignalPlay={cig_before} JobTicket={t_before}")

hdr("4. DUPLICATE INSTALL TICKET CHECK")
tickets = list(JobTicket.objects.filter(customer=cust, ticket_type="INSTALLATION"))
print(f"  Juan has {len(tickets)} INSTALLATION tickets:")
for t in tickets:
    print(f"    {t.ticket_number} {t.status:10} created={t.created_at} done={t.done_at}")
check("only ONE install ticket per customer", len(tickets) <= 1,
      f"count={len(tickets)}")

hdr("SUMMARY")
fails = [x for x in res if x[0] == BAD]
for s, l, d in res:
    print(f"  {s:8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")