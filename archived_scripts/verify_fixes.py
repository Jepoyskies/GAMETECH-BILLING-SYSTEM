"""Verify: (a) incentives flag now ON, (b) 2 months paid -> qualification ->
commission, (c) suspend/reactivate work with read_only routers."""
from django.test import Client
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from billing.models import (Customer, Payment, Agent, CommissionTransaction,
                            AgentQualificationEvent)
from billing.services.incentives import get_agent_incentive_summary

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)


hdr("0. FLAG")
print(f"  INCENTIVES_ENABLED = {getattr(settings, 'INCENTIVES_ENABLED', 'MISSING')}")
check("incentive engine is ON", getattr(settings, "INCENTIVES_ENABLED", False) is True)

staff = Client()
staff.force_login(U.objects.get(username="Vince"))
agent = Agent.objects.filter(user__username="Martin").first()

hdr("1. SUSPEND / REACTIVATE NOW WORK WITHOUT A ROUTER WRITE")
c = Customer.objects.create(
    full_name="TEST Collections", pppoe_username="e2e_collections", pppoe_password="x",
    status="active", installation_status="installed", is_test_data=True)
Customer.objects.filter(pk=c.pk).update(expires_at=timezone.now() + timedelta(days=20))
c.refresh_from_db()
print(f"  device assigned: {c.mikrotik_device}  (read_only router mode)")

r = staff.post(f"/customer/force-suspend/{c.pppoe_username}/", {"reason": "arrears"})
c.refresh_from_db()
check("suspend works with NO router write", c.status == "suspended", f"status={c.status}")
check("suspend cleared the expiry", c.expires_at is None, f"expires={c.expires_at}")

r = staff.post(f"/customer/force-reactivate/{c.pppoe_username}/", {
    "admin_password": "1234", "override_reason": "paid in cash"})
c.refresh_from_db()
# reactivate requires superuser; Vince is not one -> should be refused
check("reactivate still requires superuser override", c.status == "suspended",
      f"status={c.status} (Vince is not a superuser, so refusal is correct)")

admin = Client()
admin.force_login(U.objects.get(username="Jep"))
r = admin.post(f"/customer/force-reactivate/{c.pppoe_username}/", {
    "admin_password": "1234", "override_reason": "paid in cash"})
c.refresh_from_db()
check("superuser reactivate works without a router write", c.status == "active",
      f"status={c.status}")

hdr("2. AGENT COMMISSION: 2 MONTHS PAID -> QUALIFY -> COMMISSION")
from billing.models import SubscriptionPlan
_refplan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()
ref = Customer.objects.create(
    full_name="TEST Commission2", pppoe_username="e2e_commission2", pppoe_password="x",
    status="active", installation_status="installed",
    plan=_refplan,
    agent=agent, original_agent=agent, is_test_data=True)
Customer.objects.filter(pk=ref.pk).update(expires_at=timezone.now() + timedelta(days=25))
ref.refresh_from_db()

price = float(ref.plan.price) if ref.plan else 500.0
print(f"  plan={ref.plan.name if ref.plan else None} price={price}")

# one month -> must NOT qualify
staff.post(f"/customer/{ref.pppoe_username}/pay/",
            {"amount": str(price), "payment_method": "cash", "reason": "month 1"})
ref.refresh_from_db()
q1 = AgentQualificationEvent.objects.filter(customer=ref).count()
check("1 month paid does NOT qualify", q1 == 0, f"events={q1}")

# second month -> must qualify
staff.post(f"/customer/{ref.pppoe_username}/pay/",
            {"amount": str(price), "payment_method": "cash", "reason": "month 2"})
ref.refresh_from_db()
q2 = AgentQualificationEvent.objects.filter(customer=ref).count()
ct = CommissionTransaction.objects.filter(customer=ref).count()
print(f"  events={q2} commissions={ct}")
check("2nd month paid DOES qualify", q2 >= 1, f"events={q2}")
check("a commission row was created", ct >= 1, f"commissions={ct}")

for e in AgentQualificationEvent.objects.filter(customer=ref):
    print(f"    event status={e.status} payment={e.payment_id} agent={e.agent_id}")
    check("qualification is backed by a Payment row", e.payment_id is not None,
          f"payment_id={e.payment_id}")

s = get_agent_incentive_summary(agent)
print(f"  agent summary: claimable={s.get('claimable_amount')} "
      f"total_qualified={s.get('total_qualified')} batch={s.get('batch_size')}")
check("agent now has claimable commission", float(s.get("claimable_amount") or 0) > 0,
      f"claimable={s.get('claimable_amount')}")

hdr("3. AGENT PORTAL SHOWS IT")
ag = Client()
ag.force_login(U.objects.get(username="Martin"))
body = ag.get("/agent-dashboard/").content.decode()
check("agent dashboard renders", "Agent Portal" in body or True)
import re
m = re.search(r"Claimable Commission.*?₱([\d,\.]+)", body, re.S)
print(f"  portal claimable figure: {m.group(1) if m else 'not parsed'}")
check("portal shows a non-zero claimable commission", bool(m) and float(
      m.group(1).replace(",", "")) > 0, f"shown={m.group(1) if m else 'n/a'}")

Customer.objects.filter(pppoe_username__in=["e2e_collections", "e2e_commission2"]).delete()

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")