"""
Plan health: what would go wrong at cutover, in one list.

Two failure modes the owner specifically asked to be surfaced:

1. DUPLICATE PRICE, DIFFERENT SPEED
   `5Mbps` and `10Mbps` are both PHP 500. If the old system's export says a
   customer is on "10 Mbps", and the CRM cannot tell which of the two PHP 500
   plans is meant, the import can silently assign the wrong one -- and the
   router then carries the wrong profile.

2. NO ROUTER PROFILE MAPPED
   A plan whose `router_profile` is blank falls back to its display name, so it
   only lines up with the router if the router happens to use that exact
   string. These are the plans that will show permanent drift.

Read-only. Returns plain data so a view, an export or a command can all use it.
"""
from collections import defaultdict

from django.db.models import Count
from billing.models import Customer, SubscriptionPlan


def plan_health():
    plans = list(SubscriptionPlan.objects.all())

    by_price = defaultdict(list)
    for p in plans:
        by_price[float(p.price)].append(p)

    # --- 1. same price, different speed ---------------------------------
    ambiguous = []
    for price, group in sorted(by_price.items()):
        if len(group) < 2:
            continue
        speeds = {p.speed_mbps for p in group}
        # Only a real collision when the speeds actually differ.
        if len(speeds) > 1:
            names = [p.name for p in group]
            customer_count = Customer.objects.filter(plan__in=group).count()
            ambiguous.append({
                "price": price,
                "plans": names,
                "speeds": sorted(s for s in speeds if s is not None),
                "customer_count": customer_count,
                "problem": (
                    f"PHP {price:,.0f} is used by {len(group)} plans at different "
                    f"speeds ({', '.join(sorted(str(s) for s in speeds if s is not None))}). "
                    f"The import cannot tell which one a subscriber meant."
                ),
            })

    # --- 2. plans with no router profile mapped -------------------------
    unmapped = []
    for p in plans:
        if not (p.router_profile or "").strip():
            unmapped.append({
                "name": p.name,
                "price": float(p.price),
                "customer_count": Customer.objects.filter(plan=p).count(),
                "problem": (
                    f"'{p.name}' has no MikroTik profile set, so it falls back to "
                    f"its display name. If the router calls the profile something "
                    f"else, every customer on it shows permanent drift."
                ),
            })

    # --- 3. per-plan customer counts for the ones that matter -----------
    usage = {p.id: p.name for p in SubscriptionPlan.objects.annotate(
        n=Count("customer")).order_by("-n")[:10]}

    return {
        "ambiguous": ambiguous,
        "unmapped": unmapped,
        "total_plans": len(plans),
        "plans_with_profile": len(plans) - len(unmapped),
        "top_plans_by_customers": usage,
        "clean": not ambiguous and not unmapped,
    }


def health_summary_line():
    h = plan_health()
    if h["clean"]:
        return (f"Plan health: OK - all {h['total_plans']} plans have a router "
                f"profile and no price collisions.")
    parts = []
    if h["ambiguous"]:
        parts.append(f"{len(h['ambiguous'])} duplicate-price collision(s)")
    if h["unmapped"]:
        parts.append(f"{len(h['unmapped'])} plan(s) with no router profile")
    return "Plan health: " + ", ".join(parts) + "."