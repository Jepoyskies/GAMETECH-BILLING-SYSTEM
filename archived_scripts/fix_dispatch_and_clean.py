"""Verify the dispatch crash fix + clear the other session's test residue."""
import traceback

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory

from billing.models import Customer, Notification, Payment, SystemLog, Prospect
import dispatch.views as dv

U = get_user_model()
res = []


def check(label, ok, detail=""):
    res.append((bool(ok), label, detail))
    print(f"  [{'PASS' if ok else '**FAIL**'}] {label} {detail}")


print("=" * 74)
print("1. THE CRASH: dispatch customer detail, for a customer WITH job history")
print("=" * 74)
adm = U.objects.filter(is_staff=True).first()
with_ticket = Customer.objects.filter(job_tickets__isnull=False).distinct().first()
print(f"  customer with a job ticket: "
      f"{with_ticket.pppoe_username if with_ticket else 'none'}")
if with_ticket:
    rf = RequestFactory()
    req = rf.get("/dispatch/customers/")
    req.user = adm
    try:
        r = dv.dispatch_customer_detail_view(req, with_ticket.id)
        check("view no longer raises", True, f"HTTP {r.status_code}")
        html = r.content.decode()
        check("renders real content", len(html) > 2000, f"{len(html)} bytes")
        check("no traceback in the page", "Traceback" not in html)
    except Exception:
        check("view no longer raises", False)
        traceback.print_exc()

print()
print("=" * 74)
print("2. SAME PAGE OVER HTTP, for every customer")
print("=" * 74)
c = Client(); c.force_login(adm)
for cust in Customer.objects.all():
    try:
        r = c.get(f"/dispatch/customers/{cust.id}/")
        check(f"/dispatch/customers/{cust.id}/ ({cust.pppoe_username})",
              r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        check(f"/dispatch/customers/{cust.id}/ ({cust.pppoe_username})",
              False, f"RAISED {type(e).__name__}: {e}")

print()
print("=" * 74)
print("3. CLEAR TEST RESIDUE")
print("=" * 74)
print("  customers before:")
for x in Customer.objects.all():
    print(f"      {x.id} {x.pppoe_username} | {x.full_name} | agent={x.agent}")

# Only remove customers that are provably test rows: username contains "test".
stray = Customer.objects.filter(pppoe_username__icontains="test")
names = [x.pppoe_username for x in stray]
for x in stray:
    Payment.objects.filter(customer=x).delete()
n, _ = stray.delete()
print(f"  deleted {n} test customer row(s): {names}")

n, _ = Notification.objects.all().delete()
n2, _ = SystemLog.objects.all().delete()
print(f"  deleted {n} notification(s), {n2} systemlog row(s)")

print()
print("  customers after:")
for x in Customer.objects.all():
    print(f"      {x.id} {x.pppoe_username} | {x.full_name} | agent={x.agent}")
check("no test customers remain",
      not Customer.objects.filter(pppoe_username__icontains="test").exists())
check("alert bell is clean", Notification.objects.count() == 0)

print()
print("=" * 74)
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
print("=" * 74)
