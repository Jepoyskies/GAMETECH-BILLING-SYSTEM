"""Final state check: is anything still unfinished?"""
from collections import Counter
from datetime import timedelta

from django.utils import timezone

from billing.models import (
    Customer, Payment, Prospect, SubscriptionPlan, Notification, SystemLog,
)
from billing.services.plan_health import plan_health, health_summary_line
from network_manager.models import MikrotikDevice
from dispatch.models import JobTicket

print("=" * 76)
print("PLAN CATALOGUE")
print("=" * 76)
h = plan_health()
print(f"  {health_summary_line()}")
print(f"  mapped to a router profile : {h['plans_with_profile']}/{h['total_plans']}")
print()
inuse = Counter(Customer.objects.filter(plan__isnull=False)
                .values_list("plan__name", flat=True))
unmapped_used = [p.name for p in SubscriptionPlan.objects.all()
                 if not (p.router_profile or "").strip() and inuse.get(p.name, 0)]
print(f"  unmapped but carrying real subscribers : {unmapped_used or 'NONE'}")
print()
print("  remaining price collisions (need a business decision, not a bug):")
for a in h["ambiguous"]:
    print(f"    PHP {a['price']:>8,.0f}  {' / '.join(a['plans'])}  speeds {a['speeds']}")

print()
print("=" * 76)
print("DATA STATE")
print("=" * 76)
print(f"  customers    : {Customer.objects.count()}")
print(f"  payments     : {Payment.objects.count()}")
print(f"  job tickets  : {JobTicket.objects.count()}")
print(f"  prospects    : {Prospect.objects.count()}")
print(f"  plans        : {SubscriptionPlan.objects.count()}")
print(f"  notifications: {Notification.objects.count()}")
print(f"  systemlogs   : {SystemLog.objects.count()}")
print(f"  duplicates   : "
      f"{Customer.objects.count() - Customer.objects.exclude(pppoe_username__isnull=True).values('pppoe_username').distinct().count()}")
print(f"  no plan      : {Customer.objects.filter(plan__isnull=True).count()}")

print()
print("=" * 76)
print("THE ONE REAL OPERATIONAL ITEM LEFT: subscribers with no expiry date")
print("=" * 76)
noexp = Customer.objects.filter(expires_at__isnull=True)
print(f"  {noexp.count()} subscriber(s) will NEVER lapse on their own.")
print("  They need a date set by staff, or the line serves free indefinitely.")
print()
for c in noexp.order_by("pppoe_username")[:25]:
    print(f"    {c.pppoe_username:<28} {c.full_name[:26]:<28} "
          f"{c.get_status_display():<10} {c.get_installation_status_display()}")

print()
print("=" * 76)
print("EXPIRY SPREAD (what staff will see on day 1)")
print("=" * 76)
now = timezone.now()
buckets = {"expired": 0, "expiring<=7d": 0, "active": 0, "future": 0}
for c in Customer.objects.exclude(expires_at__isnull=True):
    d = (c.expires_at - now).days
    if d < 0:
        buckets["expired"] += 1
    elif d <= 7:
        buckets["expiring<=7d"] += 1
    elif c.status == "active":
        buckets["active"] += 1
    else:
        buckets["future"] += 1
for k, v in buckets.items():
    print(f"  {k:<16} {v:>5}")

print()
print("=" * 76)
print("ROUTERS")
print("=" * 76)
for d in MikrotikDevice.objects.annotate(n=Count("customer")):
    print(f"  {d.device_name:<32} {d.ip_address:<16} customers={d.n}")
print("=" * 76)
