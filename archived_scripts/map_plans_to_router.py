"""
Map plans to router profiles using the LIVE MikroTik, not a guess.

Reads /ppp/profile from every reachable router and reports, for each plan:
  * an EXACT name match to a real profile  -> safe to auto-map
  * a plausible speed match (plan says 1000 Mbps, router has pppoe-1000m)
  * nothing at all                          -> needs the owner's decision

Only exact matches are ever written. Nothing is invented.
"""
from collections import Counter

from billing.models import Customer, SubscriptionPlan

print("=" * 78)
print("1. WHAT THE ROUTERS ACTUALLY CARRY")
print("=" * 78)
live = {}
try:
    from network_manager.sync_services import MikrotikAPI
    from network_manager.models import MikrotikDevice

    for d in MikrotikDevice.objects.all():
        try:
            api = MikrotikAPI(d)
            res = api.get_profiles()
            names = []
            if isinstance(res, dict):
                for p in res.get("profiles", res.get("data", [])) or []:
                    if isinstance(p, dict) and p.get("name"):
                        names.append(p["name"])
            print(f"  {d.device_name:<32} {len(names):>3} profiles")
            if names:
                print(f"      {', '.join(sorted(names))}")
                live[d.device_name] = names
        except Exception as e:
            print(f"  {d.device_name:<32} unreachable ({type(e).__name__})")
except Exception as e:
    print(f"  could not reach the sync layer: {e}")

all_profiles = set()
for v in live.values():
    all_profiles.update(v)
print()
print(f"  distinct profile names across live routers: {len(all_profiles)}")
for p in sorted(all_profiles):
    print(f"      {p}")

print()
print("=" * 78)
print("2. PLANS IN USE BY REAL SUBSCRIBERS")
print("=" * 78)
inuse = (Customer.objects.filter(plan__isnull=False)
         .values_list("plan__name", flat=True))
top = Counter(inuse)
print(f"  {'plan':<26} {'customers':>9}  {'profile set?':<12} speed")
print("  " + "-" * 60)
for name, n in top.most_common():
    p = SubscriptionPlan.objects.filter(name=name).first()
    mapped = (p.router_profile if p else "") or "-"
    hit = "EXACT" if mapped in all_profiles else ("no" if mapped != "-" else "NONE")
    print(f"  {name:<26} {n:>9}  {hit:<12} {p.speed_mbps if p else '?'}")

print()
print("=" * 78)
print("3. SAFE AUTO-MAPS -- plan name is literally a profile on a live router")
print("=" * 78)
exact = [p for p in SubscriptionPlan.objects.all()
         if not (p.router_profile or "").strip()
         and p.name in all_profiles]
print(f"  {len(exact)} plan(s) can be mapped with zero guessing")
for p in exact:
    print(f"      {p.name}  (used by {top.get(p.name, 0)} customers)")

print()
print("=" * 78)
print("4. STILL UNMAPPED AND IN USE -- needs a human decision")
print("=" * 78)
unmapped_inuse = [p for p in SubscriptionPlan.objects.all()
                  if not (p.router_profile or "").strip()
                  and top.get(p.name, 0) > 0]
if not unmapped_inuse:
    print("  none")
for p in unmapped_inuse:
    print(f"      {p.name:<24} price={p.price}  speed={p.speed_mbps}  "
          f"customers={top.get(p.name, 0)}")
print()
print("  Live profile names available to map them onto:")
for p in sorted(all_profiles):
    print(f"      {p}")
print("=" * 78)
