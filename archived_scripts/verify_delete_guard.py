"""
Prove the delete-plan guard stops a router profile from being deleted while
subscribers are still on it -- the landmine that nearly fired during the merge.

Mocks the router API so we can prove it is never CALLED, without needing a
reachable router.
"""
from unittest.mock import patch

from django.db import transaction

import billing.signals as signals
from billing.models import Customer, SubscriptionPlan

res = []


def check(label, ok, detail=""):
    res.append((bool(ok), label, detail))
    print(f"  [{'PASS' if ok else '**FAIL**'}] {label} {detail}")


called = []


class FakeAPI:
    def __init__(self, device, *a, **kw):
        self.device = device

    def delete_plan_from_mikrotik(self, plan_name):
        called.append((str(self.device), plan_name))


print("=" * 74)
print("1. DELETE A PLAN THAT REAL SUBSCRIBERS ARE ON")
print("=" * 74)
target = (Customer.objects.filter(plan__isnull=False)
          .distinct().order_by("plan__id").values_list("plan", flat=True)
          .first())
target = SubscriptionPlan.objects.get(pk=target)
victim = SubscriptionPlan.objects.create(
    name=target.name, speed_up="20 Mbps", speed_down="20 Mbps",
    price=target.price, router_profile=target.router_profile,
    speed_mbps=target.speed_mbps,
)
n_on_target = Customer.objects.filter(plan=target).count()
print(f"  target plan  : id={target.id} {target.name} profile={target.router_profile!r} "
      f"({n_on_target} subscribers)")
print(f"  victim (dup) : id={victim.id} same name+profile")
print()
print(f"  >>> deleting the victim must NOT touch the router, because {n_on_target} "
      f"subscribers share its profile")

with patch.object(signals, "MikrotikAPI", FakeAPI):
    with transaction.atomic():
        victim.delete()

check("the router API was never called", not called,
      f"calls={called}")
check("no profile was deleted from any router",
      all(c[1] != target.router_profile for c in called), f"calls={called}")

print()
print("=" * 74)
print("2. DELETE A GENUINELY UNUSED PLAN -> the router cleanup SHOULD happen")
print("=" * 74)
orphan = SubscriptionPlan.objects.create(
    name="ZZZ Orphan Test Plan", speed_up="1 Mbps", speed_down="1 Mbps",
    price=1, router_profile="zzz-orphan-profile", speed_mbps=1,
)
print(f"  orphan plan id={orphan.id} profile='zzz-orphan-profile' "
      f"(nobody on it, no sibling)")
called.clear()
with patch.object(signals, "MikrotikAPI", FakeAPI):
    orphan.delete()
print(f"  router calls made: {len(called)}")
check("unused profile IS cleaned off the routers", len(called) > 0,
      f"{len(called)} call(s)")
check("and it targeted the right profile",
      any(c[1] == "zzz-orphan-profile" for c in called), f"{called[:2]}")

print()
print("=" * 74)
print("3. CLEANUP")
print("=" * 74)
print(f"  plans now: {SubscriptionPlan.objects.count()}")
print(f"  customers with no plan: {Customer.objects.filter(plan__isnull=True).count()}")
print(f"  duplicate name+price+speed rows remaining: ", end="")
from collections import defaultdict
g = defaultdict(list)
for p in SubscriptionPlan.objects.all():
    g[(p.name, float(p.price), p.speed_mbps)].append(p)
print(sum(len(v) - 1 for v in g.values() if len(v) > 1))

print()
print("=" * 74)
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
print("=" * 74)
