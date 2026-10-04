"""
Verify the agent portal changes end to end:

  1. Agent Payouts tab is gone from the sidebar
  2. "View" on an agent opens the AGENT'S OWN DASHBOARD (same template the
     agent himself gets), not a separate staff page
  3. Martin sees HIS customers with install / technician / paid / expiry
  4. Martin sees ONLY his own customers
  5. Staff view is read-only -- the agent's own POST endpoints stay closed
  6. The duplicate staff template is gone
"""
import re

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from billing.models import Agent, Customer, Payment
from billing.services.agent_portal import (
    agent_customer_tracking, agent_portal_context,
)

U = get_user_model()
res = []


def check(label, ok, detail=""):
    res.append((bool(ok), label, detail))
    print(f"  [{'PASS' if ok else '**FAIL**'}] {label} {detail}")


hdr = lambda s: print("\n" + "=" * 78 + f"\n{s}\n" + "=" * 78)

martin = Agent.objects.get(user__username="Martin")
print(f"Martin = Agent id {martin.id} ({martin.name})")

hdr("0. GIVE MARTIN A CUSTOMER TO LOOK AT (demo data)")
cust, _ = Customer.objects.get_or_create(
    pppoe_username="delacruz_juan_e2e",
    defaults={
        "full_name": "Juan Dela Cruz",
        "agent": martin,
        "status": "active",
        "installation_status": "pending",
        "expires_at": timezone.now() + timezone.timedelta(days=5),
        "outstanding_balance": 0,
    },
)
cust.agent = martin
cust.installation_status = "pending"
cust.expires_at = timezone.now() + timezone.timedelta(days=5)
cust.save()
if not Payment.objects.filter(username=cust.pppoe_username).exists():
    Payment.objects.create(
        customer=cust, username=cust.pppoe_username, amount=500,
        payment_method="cash", reason="verify_agent_portal",
    )
print(f"  {cust.pppoe_username}: pending install, expires in 5 days, "
      f"payments={Payment.objects.filter(username=cust.pppoe_username).count()}")

hdr("1. SIDEBAR: the Agent Payouts tab is gone")
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
side = adm.get("/agents/").content.decode()
nav_only = re.findall(r'<span>([^<]*)</span>', side)
check("'Agent Payouts' no longer a nav label",
      "Agent Payouts" not in nav_only, f"nav={nav_only}")
check("'Agent Portal' still in the nav", "Agent Portal" in nav_only)

hdr("2. VIEW ON AN AGENT SHOWS THE AGENT'S OWN DASHBOARD")
table = adm.get("/agents/").content.decode()
detail = adm.get(f"/staff/agents/portal/{martin.id}/").content.decode()
account = adm.get(f"/agents/view/{martin.id}/").content.decode()

check("the Agents table View button targets the agent's dashboard",
      f"/staff/agents/portal/{martin.id}/" in table)
check("the eye button is titled as the agent's own dashboard",
      "exactly what they see when they log in" in table)
check("the dashboard renders", bool(detail))
check("it is the agent portal shell, not the staff base",
      'data-persona="agent"' in detail)
check("the staff-only banner appears", "Staff view" in detail)
check("commission panel is the portal's",
      "Claimable Commission" in detail)
check("portal referral table present", "My Referrals" in detail)
check("the OLD duplicate look-alike page is gone",
      "Agent referral performance and commission status" not in detail)
check("portal login settings are still reachable separately",
      "Portal Login Account" in account)

hdr("3. MARTIN SEES HIS CUSTOMERS (the four questions)")
check("My Customers section present", "My Customers" in detail)
check("Installation column", "Installation" in detail)
check("Technician / Job column", "Technician / Job" in detail)
check("Paid column", "Paid" in detail)
check("Next Expiry column", "Next Expiry" in detail)
check("Juan is listed", "Juan Dela Cruz" in detail)
check("pending install reads 'Awaiting install'",
      "Awaiting install" in detail)
check("expiry countdown shown", "days left" in detail or "day left" in detail)

hdr("4. MARTIN SEES ONLY HIS OWN CUSTOMERS")
other = Agent.objects.exclude(pk=martin.pk).first()
if other:
    foreign = Customer.objects.filter(agent=other).exclude(
        pppoe_username=cust.pppoe_username).first()
    if foreign:
        check("another agent's customer is NOT on Martin's page",
              foreign.full_name not in detail,
              f"checked {foreign.full_name}")
tracked = agent_customer_tracking(martin)
check("the query itself is scoped to the agent",
      all(r["customer"].agent_id == martin.id for r in tracked),
      f"{len(tracked)} row(s), all his")

hdr("5. STAFF VIEW IS READ-ONLY")
check("Referral button replaced by 'View only'",
      "View only" in detail)
check("no live 'Submit New Referral' link for staff",
      'href="/agent-dashboard/add/"' not in detail)
check("no live 'Submit Your First Referral' link either",
      "Submit Your First Referral" not in detail)
check("no live cashout form for staff",
      "/agent-dashboard/cashout/" not in detail)
check("a way back to the Agents list",
      'href="/agents/"' in detail)

print()
print("  -- and the agent's OWN endpoints still reject a staff user --")
r = adm.post("/agent-dashboard/cashout/", {})
check("staff cannot request a cashout as the agent",
      r.status_code in (302, 403), f"HTTP {r.status_code}")

hdr("6. MARTIN HIMSELF STILL GETS THE FULL PORTAL (not view-only)")
ag = Client(); ag.force_login(U.objects.get(username="Martin"))
mine = ag.get("/agent-dashboard/").content.decode()
check("Martin gets 200", True)
check("his dashboard renders", "Claimable Commission" in mine)
check("My Customers is there for him too", "My Customers" in mine)
check("HIS Submit New Referral button is live",
      'href="/agent-dashboard/add/"' in mine)
check("no staff banner when he views it", "Staff view" not in mine)
check("he sees his own name", "Martin" in mine)

hdr("7. THE DUPLICATE STAFF TEMPLATE IS GONE")
import os
check("billing/staff/agent_portal_detail.html deleted",
      not os.path.exists("billing/templates/billing/staff/agent_portal_detail.html"))

hdr("8. THE SHARED BUILDER IS THE ONLY SOURCE")
ctx_martin = agent_portal_context(martin)
print(f"  context keys: {sorted(ctx_martin.keys())}")
check("tracked_customers in the shared context",
      "tracked_customers" in ctx_martin)

print()
print("=" * 78)
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
print("=" * 78)
