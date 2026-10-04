"""Drive the agent engine all the way to a cashout: 5 qualified -> eligible ->
payout batch -> paid. This is the definitive money-path test."""
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from billing.models import (Customer, Agent, AgentQualificationEvent, AgentPayoutBatch,
                            IncentiveSetting, Payment)
from billing.services.incentives import get_agent_incentive_summary, create_agent_payout_batch

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)


staff = Client()
staff.force_login(U.objects.get(username="Vince"))
agent = Agent.objects.filter(user__username="Martin").first()
from billing.models import SubscriptionPlan
plan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()
price = float(plan.price)
setting = IncentiveSetting.get_settings()
print(f"  plan={plan.name} @ {price} | incentive={setting.incentive_amount} "
      f"batch_size={setting.batch_size}")

hdr("1. CREATE 5 AGENT-REFERRED CUSTOMERS, PAY 2 MONTHS EACH")
names = []
for i in range(5):
    uname = f"e2e_agent5_{i}"
    c = Customer.objects.create(
        full_name=f"TEST Agent5 #{i}", pppoe_username=uname, pppoe_password="x",
        status="active", installation_status="installed", plan=plan,
        agent=agent, original_agent=agent, is_test_data=True)
    Customer.objects.filter(pk=c.pk).update(expires_at=timezone.now() + timedelta(days=20))
    staff.post(f"/customer/{uname}/pay/",
               {"amount": str(price), "payment_method": "cash", "reason": "m1"})
    staff.post(f"/customer/{uname}/pay/",
               {"amount": str(price), "payment_method": "cash", "reason": "m2"})
    names.append(uname)

q = AgentQualificationEvent.objects.filter(
    customer__pppoe_username__in=names, status="qualified").count()
print(f"  qualification events for the 5 test customers: {q}")
check("all 5 qualified after 2 months each", q == 5, f"count={q}")

hdr("2. INCENTIVE SUMMARY AT 5")
s = get_agent_incentive_summary(agent)
for k in ("total_qualified", "unpaid_qualified", "eligible_batches",
          "claimable_amount", "batch_payout_amount", "carry_over", "is_cashout_eligible"):
    print(f"    {k:22} {s.get(k)}")
check("cashout is now eligible", s["is_cashout_eligible"] is True)
check("claimable equals one full batch",
      float(s["claimable_amount"]) == float(s["batch_payout_amount"]),
      f"{s['claimable_amount']} vs {s['batch_payout_amount']}")

hdr("3. AGENT PORTAL SHOWS THE MONEY")
ag = Client()
ag.force_login(U.objects.get(username="Martin"))
body = ag.get("/agent-dashboard/").content.decode()
import re
m = re.search(r"Claimable Commission.*?₱([\d,\.]+)", body, re.S)
shown = m.group(1) if m else "n/a"
print(f"  portal claimable figure: {shown}")
check("portal shows a non-zero claimable commission",
      bool(m) and float(shown.replace(",", "")) > 0, f"shown={shown}")

hdr("4. CREATE THE PAYOUT BATCH")
try:
    batch = create_agent_payout_batch(agent, user=U.objects.get(username="Jep"))
    print(f"  batch = {batch}")
except Exception as e:
    print(f"  raised {type(e).__name__}: {e}")
    batch = None
check("payout batch created", batch is not None)

if batch:
    ev = AgentQualificationEvent.objects.filter(payout_batch=batch)
    print(f"  events attached: {ev.count()} | batch amount: {getattr(batch,'amount',None)} "
          f"| status: {getattr(batch,'status',None)}")
    check("exactly batch_size events attached", ev.count() == setting.batch_size,
          f"{ev.count()} vs {setting.batch_size}")

    s2 = get_agent_incentive_summary(agent)
    print(f"  after batch: claimable={s2['claimable_amount']} "
          f"unpaid={s2['unpaid_qualified']} eligible={s2['is_cashout_eligible']}")
    check("claimable resets after the batch is created", float(s2["claimable_amount"]) == 0)

hdr("5. PAY THE BATCH")
r = staff.post(f"/agents/payouts/mark-paid/{batch.id}/", {"reference_no": "E2E-PAYOUT-001"})
print(f"  POST /agents/payouts/mark-paid/ -> {r.status_code} {r.headers.get('Location','')}")
batch.refresh_from_db()
print(f"  batch status now: {batch.status} paid_at={batch.paid_at}")
check("batch marked paid", str(getattr(batch, "status", "")).lower() in ("paid", "completed"),
      f"status={batch.status}")

for u in names:
    AgentQualificationEvent.objects.filter(customer__pppoe_username=u).delete()
Customer.objects.filter(pppoe_username__in=names).delete()
if batch:
    batch.delete()

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")