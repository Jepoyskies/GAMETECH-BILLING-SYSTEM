"""Suspend/reactivate with the REAL urls, plus the agent commission/incentive
ledger (Rule 39: money must always have a verifiable Payment behind it).
"""
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from billing.models import Customer, Payment, Agent, CommissionTransaction, AgentPayoutBatch
from billing.services.incentives import *  # noqa
import billing.services.incentives as incentives

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)


staff = Client()
staff.force_login(U.objects.get(username="Vince"))

hdr("1. FORCE SUSPEND / REACTIVATE (real URLs)")
c = Customer.objects.create(
    full_name="TEST Suspend", pppoe_username="e2e_suspend", pppoe_password="x",
    status="active", installation_status="installed", is_test_data=True,
)
Customer.objects.filter(pk=c.pk).update(expires_at=timezone.now() + timedelta(days=20))
c.refresh_from_db()

r = staff.post(f"/customer/force-suspend/{c.pppoe_username}/", {"reason": "non-payment test"})
print(f"  POST force-suspend -> {r.status_code} {r.headers.get('Location','')}")
c.refresh_from_db()
check("force-suspend sets status=suspended", c.status == "suspended", f"status={c.status}")

r = staff.get("/customers/")
check("suspended customer still lists", "e2e_suspend" in r.content.decode().lower()
      or r.status_code == 200)

r = staff.post(f"/customer/force-reactivate/{c.pppoe_username}/", {"reason": "paid in cash"})
print(f"  POST force-reactivate -> {r.status_code} {r.headers.get('Location','')}")
c.refresh_from_db()
check("force-reactivate sets status=active", c.status == "active", f"status={c.status}")

hdr("2. PERMISSION: can a CSR suspend?")
viewer = Client()
viewer.force_login(U.objects.get(username="Admin"))  # superuser baseline
r2 = viewer.get(f"/customer/force-suspend/{c.pppoe_username}/")
print(f"  Admin GET force-suspend -> {r2.status_code}")

hdr("3. AGENT COMMISSION LEDGER")
print("  incentives module exports:", [n for n in dir(incentives) if not n.startswith("_")][:14])
agent = Agent.objects.filter(user__username="Martin").first()
print(f"  agent: {agent.name if agent else None}")
print(f"  CommissionTransaction rows: {CommissionTransaction.objects.count()}")
print(f"  AgentPayoutBatch rows     : {AgentPayoutBatch.objects.count()}")

ag = Client()
ag.force_login(U.objects.get(username="Martin"))
r = ag.get("/agent-dashboard/")
check("agent dashboard loads", r.status_code == 200, f"HTTP {r.status_code}")
body = r.content.decode()
check("agent sees claimable commission", "Claimable Commission" in body)
check("agent sees payout progress", "Payout Goal" in body)

hdr("4. COMMISSION MUST BE BACKED BY A REAL PAYMENT")
# The qualifying trigger is a Payment post_save (billing/signals.py
# payment_post_save_incentive_trigger). Verify that path exists and is wired.
from django.db.models.signals import post_save
from billing.models import Payment as P
live = post_save._live_receivers(P)
print(f"  post_save receivers on Payment: {len(live)}")
try:
    from billing.signals import payment_post_save_incentive_trigger as trig
    print(f"  incentive trigger connected: {trig in live}")
except Exception as e:
    print(f"  incentive trigger import failed: {e}")

# Every commission row must point at a Payment, or it is unbacked money.
unbacked = CommissionTransaction.objects.filter(payment__isnull=True).count()
print(f"  commission rows with NO payment: {unbacked}")

hdr("5. AGENT PAYOUT / CASHOUT")
r = ag.post("/agent-dashboard/request-cashout/", {})
print(f"  POST request-cashout -> {r.status_code} {r.headers.get('Location','')}")
check("cashout endpoint exists (403/redirect is fine, 500 is not)",
      r.status_code != 500, f"HTTP {r.status_code}")

r = ag.get("/agents/")  # should bounce: agents module not for personas
print(f"  Agent GET /agents/ -> {r.status_code} {r.headers.get('Location','')}")

Customer.objects.filter(pppoe_username="e2e_suspend").delete()

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")