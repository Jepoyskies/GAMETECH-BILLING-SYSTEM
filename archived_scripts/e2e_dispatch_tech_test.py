"""
Part 2 of the end-to-end probe: CSR assigns -> Technician works the job ->
CSR verifies the customer went active. This is the step that proves the
Dispatch -> CRM direction actually writes back.
"""

import json
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import Customer
from dispatch.models import JobTicket

User = get_user_model()
OK, BAD = "PASS", "**FAIL**"
results = []


def check(label, cond, detail=""):
    results.append((OK if cond else BAD, label, detail))
    print(f"  [{OK if cond else BAD}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 72 + f"\n{s}\n" + "=" * 72)


def body_of(resp):
    try:
        return json.loads(resp.content.decode())
    except Exception:
        return {"_raw": resp.content.decode()[:300]}


cust = Customer.objects.filter(pppoe_username="delacruz_juan_e2e").first()
if not cust:
    raise SystemExit("ABORT: run part 1 first")
ticket = JobTicket.objects.filter(customer=cust).first()
tech = User.objects.get(username="Merk")
tech_profile = tech.technician

hdr("4. CSR assigns the ticket to Merk")
vince = Client()
vince.force_login(User.objects.get(username="Vince"))
r = vince.post(f"/dispatch/api/tickets/{ticket.id}/assign/",
               data=json.dumps({"technician_ids": [tech_profile.id]}),
               content_type="application/json")
print(f"  assign HTTP {r.status_code} -> {body_of(r)}")
ticket.refresh_from_db()
assigned = ticket.technicians.filter(id=tech_profile.id).exists()
check("ticket assigned to Merk", assigned,
      f"techs={[t.name for t in ticket.technicians.all()]} status={ticket.status}")

hdr("5. TECHNICIAN sees it, works it, completes it")
merk = Client()
merk.force_login(tech)

r = merk.get("/dispatch/my-jobs/")
check("tech my-jobs renders", r.status_code == 200, f"HTTP {r.status_code}")
check("tech sees the customer name on his job list", "Juan Dela Cruz" in r.content.decode())

ticket.refresh_from_db()
print(f"  ticket before tech work: status={ticket.status} technicians={[t.name for t in ticket.technicians.all()]}")

r = merk.post(f"/dispatch/api/tickets/{ticket.id}/arrived/",
              data=json.dumps({}), content_type="application/json")
print(f"  arrived HTTP {r.status_code} -> {body_of(r)}")
ticket.refresh_from_db()
print(f"  ticket after arrive: status={ticket.status}")

r = merk.post(f"/dispatch/api/tickets/{ticket.id}/complete/",
              data=json.dumps({
                  "remarks": "Fiber drop installed, ONU powered, PPPoE profile verified on site.",
                  "mac_address": "AA:BB:CC:DD:EE:01",
                  "serial_number": "SN-E2E-0001",
              }),
              content_type="application/json")
print(f"  complete HTTP {r.status_code} -> {body_of(r)}")
ticket.refresh_from_db()
print(f"  ticket after complete: status={ticket.status}")

hdr("6. CSR VERIFIES the customer went active")
vince2 = Client()
vince2.force_login(User.objects.get(username="Vince"))
r = vince2.get("/customers/")
check("customer list renders for CSR", r.status_code == 200, f"HTTP {r.status_code}")
body = r.content.decode()
check("Juan appears in the customer list", "Juan Dela Cruz" in body)

r = vince2.get(f"/customers/view/{cust.id}/")
check("customer detail page renders", r.status_code == 200, f"HTTP {r.status_code}")
detail = r.content.decode()
check("detail shows active", ">Active<" in detail or "Active" in detail)

print(f"\n  FINAL STATE")
print(f"    customer #{cust.id}: status={cust.status} installation={cust.installation_status} installed_at={cust.installed_at} expires_at={cust.expires_at}")
print(f"    ticket {ticket.ticket_number}: status={ticket.status} done_at={ticket.done_at}")

hdr("SUMMARY")
fails = [x for x in results if x[0] == BAD]
for s, l, d in results:
    print(f"  {s:8} {l} {d}")
print(f"\n  {len(results)-len(fails)}/{len(results)} passed")