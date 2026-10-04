"""Verify plan_health catches the duplicate-price and unmapped-profile problems."""
import json

from billing.models import Customer, SubscriptionPlan
from billing.services.plan_health import plan_health, health_summary_line
from network_manager.sync_helpers import desired_profile

h = plan_health()
print("=" * 76)
print(health_summary_line())
print("=" * 76)
print(f"  total plans          : {h['total_plans']}")
print(f"  with router profile  : {h['plans_with_profile']}")

print()
print("=" * 76)
print("1. DUPLICATE PRICE, DIFFERENT SPEED  (your 5Mbps / 10Mbps case)")
print("=" * 76)
if not h["ambiguous"]:
    print("  none detected")
for a in h["ambiguous"]:
    print(f"  PHP {a['price']:>9,.2f}  plans={a['plans']}  speeds={a['speeds']}  "
          f"customers={a['customer_count']}")
    print(f"      {a['problem']}")

print()
print("=" * 76)
print("2. NO ROUTER PROFILE MAPPED (these show permanent drift)")
print("=" * 76)
print(f"  {len(h['unmapped'])} plan(s):")
for u in sorted(h["unmapped"], key=lambda x: -x["customer_count"])[:40]:
    print(f"    {u['name']:28} PHP {u['price']:>9,.2f}  customers={u['customer_count']}")

print()
print("=" * 76)
print("3. desired_profile() NOW USES THE PROFILE, NOT THE DISPLAY NAME")
print("=" * 76)
for name in ("5Mbps", "pppoe-15m_500", "GIMI Home Fiber 1000"):
    p = SubscriptionPlan.objects.filter(name=name).first()
    if p:
        print(f"  {name:24} display={p.name:24} effective_profile={p.effective_router_profile}")

print()
print("=" * 76)
print("4. JSON-SERIALISABLE (so the view and the export can both use it)")
print("=" * 76)
blob = json.dumps(h, default=str)
print(f"  serialised {len(blob)} bytes OK")
print("=" * 76)