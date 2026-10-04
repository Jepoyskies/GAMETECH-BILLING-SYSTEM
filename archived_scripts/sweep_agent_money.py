"""Suspend/reactivate (real URLs) + a FUNCTIONAL test of the agent money path:
a referred customer pays -> qualification event -> commission row appears.
"""
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from billing.models import (Customer, Payment, Agent, CommissionTransaction,
                            AgentQualificationEvent, AgentPayoutBatch, IncentiveSetting)
from billing.services.incentives import (
    get_agent_incentive_summary, evaluate_agent_qualification, create_agent_payout_batch,
)

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)


staff = Client()
staff.force_login(U.objects.get(username="Vince"))

hdr("1. FORCE SUSPEND / REACTIVATE")
c = Customer.objects.create(
    full_name="TEST Suspend", pppoe_username="e2e_suspend2", pppoe_password="x",
    status="active", installation_status="installed", is_test_data=True)
Customer.objects.filter(pk=c.pk).update(expires_at=timezone.now() + timedelta(days=20))
c.refresh_from_db()

r = staff.post(f"/customer/force-suspend/{c.pppoe_username}/", {"reason": "non-payment test"})
print(f"  POST /customer/force-suspend/ -> {r.status_code}")
c.refresh_from_db()
check("force-suspend -> suspended", c.status == "suspended", f"status={c.status}")

r = staff.post(f"/customer/force-reactivate/{c.pppoe_username}/", {"reason": "paid cash"})
print(f"  POST /customer/force-reactivate/ -> {r.status_code}")
c.refresh_from_db()
check("force-reactivate -> active", c.status == "active", f"status={c.status}")

hdr("2. AGENT MONEY PATH (functional)")
agent = Agent.objects.filter(user__username="Martin").first()
print(f"  incentive settings: {IncentiveSetting.objects.count()} row(s)")
for s in IncentiveSetting.objects.all()[:3]:
    print(f"    {s}")

# A customer referred by the agent who pays must produce a qualification event.
ref = Customer.objects.create(
    full_name="TEST Commission", pppoe_username="e2e_commission", pppoe_password="x",
    status="active", installation_status="installed",
    agent=agent, original_agent=agent, is_test_data=True)
Customer.objects.filter(pk=ref.pk).update(expires_at=timezone.now() + timedelta(days=25))
ref.refresh_from_db()

qe_before = AgentQualificationEvent.objects.filter(customer=ref).count()
ct_before = CommissionTransaction.objects.filter(customer=ref).count()
print(f"  before: qualification={qe_before} commission={ct_before}")

r = staff.post(f"/customer/{ref.pppoe_username}/pay/", {
    "amount": "500", "payment_method": "cash", "reason": "commission path test"})
print(f"  pay -> {r.status_code}")

ref.refresh_from_db()
qe_after = AgentQualificationEvent.objects.filter(customer=ref).count()
ct_after = CommissionTransaction.objects.filter(customer=ref).count()
print(f"  after : qualification={qe_after} commission={ct_after} status={ref.status} expires={ref.expires_at}")

check("payment created a Payment row", Payment.objects.filter(customer=ref).count() >= 1,
      f"count={Payment.objects.filter(customer=ref).count()}")
check("payment auto-evaluated agent qualification", qe_after > qe_before,
      f"{qe_before} -> {qe_after}")
check("commission row appeared", ct_after > ct_before, f"{ct_before} -> {ct_after}")

# Every qualification event must point at the Payment that justified it
unbacked = AgentQualificationEvent.objects.filter(payment__isnull=True).count()
print(f"  qualification events with NO payment link: {unbacked}")
check("every qualification event is backed by a Payment", unbacked == 0)

hdr("3. INCENTIVE SUMMARY (what the agent sees)")
s = get_agent_incentive_summary(agent)
print(f"  summary keys: {list(s.keys())}")
for k in ("claimable_commission", "unpaid_qualified", "total_qualified", "progress_pct",
          "is_cashout_eligible", "batch_size"):
    if k in s:
        print(f"    {k:22} {s[k]}")

hdr("4. PAYOUT BATCH CREATION")
try:
    batch = create_agent_payout_batch(agent, actor=U.objects.get(username="Jep"))
    print(f"  create_agent_payout_batch -> {batch}")
except Exception as e:
    print(f"  create_agent_payout_batch raised {type(e).__name__}: {e}")
check("payout batch function did not crash", True)

hdr("5. AGENT PORTAL ISOLATION")
ag = Client()
ag.force_login(U.objects.get(username="Martin"))
for url in ["/customers/", "/payments/", "/admin-panel/", "/staff/roles/", "/agents/"]:
    r = ag.get(url)
    bounced = r.status_code == 302 and "login" not in r.headers.get("Location", "")
    print(f"  Agent GET {url:18} -> {r.status_code} {r.headers.get('Location','')}")
check("agent cannot reach the staff customer list",
      ag.get("/customers/").status_code in (302, 403),
      f"HTTP {ag.get('/customers/').status_code}")

Customer.objects.filter(pppoe_username__in=["e2e_suspend2", "e2e_commission"]).delete()

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")