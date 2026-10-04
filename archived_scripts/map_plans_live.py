"""
Read the REAL /ppp/profile list off every reachable router and map plans to it.

Correct constructor this time: MikrotikAPI(ip, username, password, port).
Only exact name matches are ever written to a plan -- nothing is invented.
"""
from collections import Counter

from django.conf import settings
from billing.models import Customer, SubscriptionPlan
from network_manager.models import MikrotikDevice
from network_manager.sync_services import MikrotikAPI

print("=" * 78)
print(f"ROUTER_MODE = {getattr(settings, 'ROUTER_MODE', '?')}")
print("=" * 78)

live = {}
for d in MikrotikDevice.objects.all():
    try:
        api = MikrotikAPI(d.ip_address, d.api_username, d.api_password,
                          d.api_port)
        api.device = d
        _, conn = api._get_api_connection()
        profiles = conn.get_resource("/ppp/profile").get()
        names = sorted({p.get("name") for p in profiles if p.get("name")})
        print(f"  {d.device_name:<32} {len(names):>3} profiles")
        live[d.device_name] = names
        # Also read the active secrets so we know what is really provisioned.
        try:
            secrets = conn.get_resource("/ppp/secret").get()
            print(f"      {len(secrets)} active PPPoE secrets on the router")
        except Exception:
            pass
    except Exception as e:
        print(f"  {d.device_name:<32} -- {type(e).__name__}: {str(e)[:70]}")

all_profiles = set()
for v in live.values():
    all_profiles.update(v)

print()
print(f"distinct profile names across live routers: {len(all_profiles)}")
for p in sorted(all_profiles):
    print(f"    {p}")

print()
print("=" * 78)
print("PLAN -> PROFILE MAPPING")
print("=" * 78)
inuse = Counter(Customer.objects.filter(plan__isnull=False)
                .values_list("plan__name", flat=True))

exact, unmapped_inuse = [], []
for p in SubscriptionPlan.objects.all():
    mapped = (p.router_profile or "").strip()
    n = inuse.get(p.name, 0)
    if mapped:
        continue
    if p.name in all_profiles:
        exact.append((p, n))
    elif n > 0:
        unmapped_inuse.append((p, n))

print(f"-- EXACT matches (safe to write, zero guessing): {len(exact)} --")
for p, n in exact:
    print(f"     {p.name:<30} customers={n}")

print()
print(f"-- used by real subscribers but UNMAPPED: {len(unmapped_inuse)} --")
for p, n in sorted(unmapped_inuse, key=lambda x: -x[1]):
    print(f"     {p.name:<28} price={p.price} speed={p.speed_mbps} "
          f"customers={n}")

print()
print("=" * 78)
if exact:
    print("WRITING the exact matches (this changes what the sync pushes)")
    print("=" * 78)
    for p, n in exact:
        p.router_profile = p.name
        p.save(update_fields=["router_profile"])
        print(f"     {p.name} -> {p.name}  ({n} customers)")
    print()
    print("Re-read plan health:")
    from billing.services.plan_health import plan_health, health_summary_line
    h = plan_health()
    print(f"     {health_summary_line()}")
    still = [q.name for q in SubscriptionPlan.objects.all()
             if not (q.router_profile or "").strip()
             and inuse.get(q.name, 0) > 0]
    print(f"     unmapped and in use: {still or 'none'}")
else:
    print("No exact matches -- every unmapped plan needs an explicit decision.")
print("=" * 78)
