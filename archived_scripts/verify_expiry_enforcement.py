"""
THE QUESTION THAT MATTERS FOR TOMORROW'S CUTOVER:

If the old system disconnects and a subscriber's expires_at is in the past,
does the new system NOTICE -- or do they silently keep free internet?

auto_suspend is NOT scheduled, so nothing runs nightly. The answer must come
from the customer list / lifecycle resolution reading expires_at directly.
"""
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from billing.models import Customer, SubscriptionPlan
import billing.customer_state as CS

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


plan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()

hdr = lambda s: print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)

hdr("1. BUILD A LAPSED SUBSCRIBER (expired 5 days ago, still active)")
uname = "e2e_lapsed"
Customer.objects.filter(pppoe_username=uname).delete()
c = Customer.objects.create(
    full_name="Lapsed Probe", pppoe_username=uname, pppoe_password="Lapse123",
    status="active", installation_status="installed", plan=plan,
    is_test_data=False)
Customer.objects.filter(pk=c.pk).update(expires_at=timezone.now() - timedelta(days=5))
c.refresh_from_db()
print(f"  expires_at = {c.expires_at}  status = {c.status}")

hdr("2. IS ANY SCHEDULED JOB GOING TO CATCH THIS?")
from django.conf import settings
sched = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
tasks = [e.get("task") for e in sched.values()]
print(f"  scheduled tasks: {tasks}")
check("no scheduled task marks customers expired",
      not any("suspend" in (t or "") or "expire" in (t or "") for t in tasks),
      "confirmed: nothing runs nightly")
check("customer status is STILL 'active' (nobody changed it)",
      c.status == "active", f"status={c.status}")

hdr("3. BUT DOES THE CUSTOMER LIST FLAG IT? (this is the safety net)")
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
page = adm.get("/customers/?q=e2e_lapsed").content.decode()
check("the lapsed customer is findable in the list", "e2e_lapsed" in page or "Lapsed" in page)
for probe in ("Connected, Unpaid", "Unpaid", "Expired", "Overdue", "Lapsed", "No Expiry"):
    print(f"  page mentions {probe!r}: {probe.lower() in page.lower()}")

hdr("4. IS THERE A ONE-CLICK QUEUE FOR IT?")
qs = [
    "/customers/?status=expired",
    "/customers/?lifecycle=connected_unpaid",
    "/customers/?view=connected_unpaid",
    "/customers/?connected=1&expired=1",
    "/customers/?issues=1",
    "/customers/?filter=connected_unpaid",
]
for u in qs:
    r = adm.get(u, follow=False)
    print(f"  {u:44} -> {r.status_code}")

hdr("5. LIFECYCLE RESOLUTION (the logic behind the badges)")
try:
    st = CS.resolve(c, set())
    print(f"  resolved: key={getattr(st,'key',None)} label={getattr(st,'label',None)} "
          f"billing={getattr(st,'billing',None)} hardware={getattr(st,'hardware',None)} "
          f"actionable={getattr(st,'actionable',None)}")
    check("the lapsed customer resolves to an actionable state",
          bool(getattr(st, "actionable", False)),
          f"key={getattr(st,'key',None)}")
except Exception as e:
    print(f"  resolve_state unavailable: {type(e).__name__}: {e}")
    import inspect
    from billing import customer_state as cs
    print("  exports:", [n for n in dir(CS) if not n.startswith("_")][:25])

hdr("6. VERDICT")
print("  A lapsed customer is NOT auto-expired (no scheduler), but the list/lifecycle")
print("  is designed to surface them as 'Connected, Unpaid' for a human. Question is")
print("  whether that is visible enough, given nobody runs a nightly sweep.")

Customer.objects.filter(pppoe_username=uname).delete()

print()
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
