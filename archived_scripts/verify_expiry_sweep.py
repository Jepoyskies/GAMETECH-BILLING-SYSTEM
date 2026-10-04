"""Verify the nightly expiry sweep: lapsed-but-online customers are flagged,
advance payment auto-renews, and NOTHING is written to any router."""
import json
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from billing.models import Customer, SubscriptionPlan, Notification, SystemLog, Payment
from billing.services.expiry_sweep import sweep_expiry
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


hdr = lambda s: print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)

plan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()
dev = MikrotikDevice.objects.filter(device_name="Mikrotik A").first()


def router_state():
    if not dev:
        return {}
    api = MikrotikAPI(dev)
    return {s.get("name"): str(s.get("disabled")).lower()
            for s in api._get_api().get_resource("/ppp/secret").get() or []}


hdr("1. BUILD TWO PROBES: one lapsed, one lapsed WITH advance payment")
base = router_state()
Notification.objects.filter(notification_type="billing").delete()

a = Customer.objects.create(full_name="Sweep Lapsed", pppoe_username="e2e_sweep_a",
                            pppoe_password="SweepA123", status="active",
                            installation_status="installed", plan=plan,
                            is_test_data=False)
Customer.objects.filter(pk=a.pk).update(expires_at=timezone.now() - timedelta(days=10))

b = Customer.objects.create(full_name="Sweep Advance", pppoe_username="e2e_sweep_b",
                            pppoe_password="SweepB123", status="active",
                            installation_status="installed", plan=plan,
                            outstanding_balance=-float(plan.price) * 2,
                            is_test_data=False)
Customer.objects.filter(pk=b.pk).update(expires_at=timezone.now() - timedelta(days=10))

a.refresh_from_db(); b.refresh_from_db()
print(f"  A: {a.pppoe_username} expires={a.expires_at} balance={a.outstanding_balance}")
print(f"  B: {b.pppoe_username} expires={b.expires_at} balance={b.outstanding_balance}")

hdr("2. RUN THE SWEEP")
result = sweep_expiry()
print(f"  result: {result}")
check("sweep found the lapsed customers", result["past_due"] >= 2, f"past_due={result['past_due']}")
check("advance payment auto-renewed", result["renewed"] >= 1, f"renewed={result['renewed']}")

b.refresh_from_db()
check("advance customer got a new future expiry", b.expires_at and b.expires_at > timezone.now(),
      f"expires={b.expires_at}")
check("advance deduction logged as a Payment",
      Payment.objects.filter(reference_no="AUTO-RENEW", customer=b).count() >= 1)

a.refresh_from_db()
check("lapsed customer NOT auto-suspended (human decides)",
      a.status == "active", f"status={a.status}")
check("lapsed customer still past due", a.expires_at < timezone.now(),
      f"expires={a.expires_at}")

hdr("3. STAFF WERE TOLD")
notifs = Notification.objects.filter(notification_type="billing")
check("a notification was raised", notifs.count() >= 1, f"count={notifs.count()}")
for n in notifs[:2]:
    print(f"     {n.title} -> {n.link}")
    print(f"       {n.message[:150]}")

hdr("4. NOTHING WAS WRITTEN TO ANY ROUTER")
after = router_state()
check("router byte-identical before and after the sweep", after == base,
      f"added={set(after)-set(base)}")
check("no probe secret appeared on the router",
      "e2e_sweep_a" not in after and "e2e_sweep_b" not in after)

hdr("5. IT IS SCHEDULED")
from django.conf import settings
sched = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
check("expiry sweep is in the beat schedule", "expiry-sweep-nightly" in sched,
      f"jobs={list(sched)}")
check("auto_suspend is STILL not scheduled (safety rule kept)",
      not any("auto_suspend" in (e.get("task") or "") for e in sched.values()))

hdr("6. THE 'Connected, Unpaid' QUEUE RESOLVES FOR A ROUTER-BOUND SUBSCRIBER")
from billing.customer_state import resolve
if dev:
    cust = Customer.objects.create(full_name="Queue Probe", pppoe_username="e2e_queue",
                                   pppoe_password="Q1234567", status="active",
                                   installation_status="installed", plan=plan,
                                   mikrotik_device=dev, is_test_data=False)
    Customer.objects.filter(pk=cust.pk).update(expires_at=timezone.now() - timedelta(days=3))
    cust.refresh_from_db()
    st = resolve(cust, {cust.pppoe_username})
    print(f"  resolved -> key={st.key} label={st.label} billing={st.billing} "
          f"hardware={st.hardware} priority={st.priority}")
    check("a past-due online subscriber lands in an actionable state", st.actionable,
          f"key={st.key}")
    cust.delete()

Customer.objects.filter(pppoe_username__in=["e2e_sweep_a", "e2e_sweep_b"]).delete()

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")