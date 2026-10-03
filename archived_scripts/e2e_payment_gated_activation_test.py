"""
Proves the corrected business rule:

    install completed  ->  installed, but STILL 'pending', expires_at = None
    CSR records payment ->  'active' AND expires_at set, together

Before this fix the technician's Done click alone set status='active' with no
payment and no due date.
"""

import json
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from billing.models import Customer, Payment
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
    raise SystemExit("ABORT: run part 1 first")

# Reset to the post-install, pre-payment state this rule is about.
Customer.objects.filter(pk=cust.pk).update(
    status="pending", installation_status="pending", expires_at=None,
    installed_at=None, first_payment_date=None,
)
Payment.objects.filter(customer=cust).delete()
cust.refresh_from_db()
ticket = JobTicket.objects.filter(customer=cust).first()
ticket.status = "IN_PROGRESS"
ticket.save()

hdr("A. Technician completes the job (no payment yet)")
merk = Client()
merk.force_login(User.objects.get(username="Merk"))
r = merk.post(f"/dispatch/api/tickets/{ticket.id}/complete/",
              data=json.dumps({"remarks": "Fibre installed, awaiting first payment."}),
              content_type="application/json")
print(f"  complete HTTP {r.status_code}")
ticket.refresh_from_db()
print(f"  ticket status = {ticket.status}")

cust.refresh_from_db()
print(f"\n  customer: status={cust.status} installation={cust.installation_status} expires_at={cust.expires_at}")
check("installed physically", cust.installation_status == "installed")
check("NOT activated by the technician", cust.status == "pending", f"status={cust.status}")
check("no due date invented", cust.expires_at is None)
check("no payment row exists", Payment.objects.filter(customer=cust).count() == 0)

hdr("B. CSR opens the profile and records the payment")
vince = Client()
vince.force_login(User.objects.get(username="Vince"))
r = vince.get(f"/customer/{cust.pppoe_username}/pay/")
check("CSR can open the pay screen", r.status_code == 200, f"HTTP {r.status_code}")

price = float(cust.plan.price) if cust.plan else 500.0
r = vine_post = vince.post(f"/customer/{cust.pppoe_username}/pay/", {
    "amount": str(price),
    "payment_method": "cash",
    "reference_no": "E2E-CASH-001",
    "reason": "First monthly subscription - collected at install",
})
print(f"  pay HTTP {r.status_code}")

cust.refresh_from_db()
print(f"\n  customer: status={cust.status} expires_at={cust.expires_at} first_payment={cust.first_payment_date}")
check("payment row written", Payment.objects.filter(customer=cust).count() >= 1,
      f"count={Payment.objects.filter(customer=cust).count()}")
check("ACTIVATED by the payment", cust.status == "active", f"status={cust.status}")
check("due date set", cust.expires_at is not None, f"expires_at={cust.expires_at}")
check("due date is in the future",
      cust.expires_at is not None and cust.expires_at > timezone.now())
check("first_payment_date recorded", cust.first_payment_date is not None)

hdr("C. Regression: a returning/repair customer is still activatable")
# Simulate a customer who HAS paid before -- approving must still set active.
JobTicket.objects.filter(customer=cust).update(status="IN_PROGRESS")
vince.post(f"/dispatch/api/tickets/{ticket.id}/complete/",
           data=json.dumps({"remarks": "re-visit"}), content_type="application/json")
cust.refresh_from_db()
check("paying customer stays/becomes active (no regression)", cust.status == "active",
      f"status={cust.status}")
check("awaiting_first_payment is now False", cust.awaiting_first_payment is False)

hdr("SUMMARY")
fails = [x for x in res if x[0] == BAD]
for s, l, d in res:
    print(f"  {s:8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
if fails:
    print("  FAILURES PRESENT")