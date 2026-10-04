"""
Find and merge duplicate SubscriptionPlan rows.

The importer and the plan editor both created plans keyed on name, so the
catalogue ended up with rows like TWO plans both called "GTipid Fiber 1000" at
the same price and speed. Staff see the same plan twice in the picker and a new
customer lands on whichever row the query happened to return first.

Merge rule (conservative, nothing is deleted that holds data):
  * group by exact (name, price, speed_mbps)
  * keep the LOWEST id
  * move every customer, payment reference and add-on onto the survivor
  * delete the empty duplicates
  * never merge plans whose names differ, even at the same price
"""
from collections import defaultdict

from django.db import transaction

from billing.models import Customer, SubscriptionPlan

print("=" * 76)
print("1. DUPLICATE PLAN ROWS (identical name + price + speed)")
print("=" * 76)
groups = defaultdict(list)
for p in SubscriptionPlan.objects.all().order_by("id"):
    groups[(p.name, float(p.price), p.speed_mbps)].append(p)

dupes = {k: v for k, v in groups.items() if len(v) > 1}
if not dupes:
    print("  none")
for (name, price, speed), plans in sorted(dupes.items()):
    print(f"  {name!r} @ PHP {price:,.2f} @ {speed} Mbps  x{len(plans)}")
    for p in plans:
        n = Customer.objects.filter(plan=p).count()
        print(f"      id={p.id:<6} profile={p.router_profile or '-':<24} "
              f"customers={n}")

print()
print("=" * 76)
print("2. ALSO CHECK: same name, DIFFERENT price (worse -- not a clean merge)")
print("=" * 76)
byname = defaultdict(list)
for p in SubscriptionPlan.objects.all().order_by("id"):
    byname[p.name].append(p)
split = {k: v for k, v in byname.items() if len({float(x.price) for x in v}) > 1}
if not split:
    print("  none")
for name, plans in split.items():
    print(f"  {name!r}:")
    for p in plans:
        print(f"      id={p.id:<6} price={p.price} speed={p.speed_mbps} "
              f"customers={Customer.objects.filter(plan=p).count()}")

print()
print("=" * 76)
print("3. MERGING (transactional -- all or nothing)")
print("=" * 76)
if not dupes:
    print("  nothing to merge")
with transaction.atomic():
    merged = 0
    for (name, price, speed), plans in sorted(dupes.items()):
        keep = plans[0]
        for dead in plans[1:]:
            moved = Customer.objects.filter(plan=dead).update(plan=keep)
            # Carry over a router profile if only the survivor lacks one.
            if not (keep.router_profile or "").strip() and (dead.router_profile or "").strip():
                keep.router_profile = dead.router_profile
                keep.save(update_fields=["router_profile"])
            if dead.pk is not None:
                dead.delete()
            merged += 1
            print(f"  merged id={dead.id} into id={keep.id} "
                  f"({name}, moved {moved} customer(s))")
    print(f"  {merged} duplicate row(s) removed")

print()
print("=" * 76)
print("4. AFTER")
print("=" * 76)
print(f"  plans: {SubscriptionPlan.objects.count()}")
print(f"  customers with no plan: {Customer.objects.filter(plan__isnull=True).count()}")
from billing.services.plan_health import plan_health, health_summary_line
h = plan_health()
print(f"  {health_summary_line()}")
print(f"  mapped: {h['plans_with_profile']}/{h['total_plans']}")
for a in h["ambiguous"]:
    print(f"    STILL AMBIGUOUS: PHP {a['price']:,.0f} {a['plans']} {a['speeds']}")
print("=" * 76)
