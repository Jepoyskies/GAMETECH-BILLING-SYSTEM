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
    #
    # This started as a blunt "same price + different speed = problem" warning
    # and it cried wolf. The real catalogue sells several tiers at one price,
    # each named for its own speed -- "GTipid Fiber 500 (10 Mbps)" next to
    # "GTipid Fiber 500 (15 Mbps)". Those are legitimate product variants and the
    # name already says which is which.
    #
    # Two tiers are only genuinely ambiguous when the NAMES do not distinguish
    # them. So that is the only thing worth raising:
    #   * same price AND same speed  -> a true duplicate, one of them is dead
    #   * same price, different speed, but indistinguishable names -> ambiguous
    variants = []
    ambiguous = []
    for price, group in sorted(by_price.items()):
        if len(group) < 2:
            continue

        # A true duplicate: identical price AND identical speed.
        by_speed = {}
        for p in group:
            by_speed.setdefault(p.speed_mbps, []).append(p)
        for speed, same in sorted(by_speed.items(),
                                  key=lambda kv: (kv[0] is None, kv[0])):
            if len(same) > 1:
                ambiguous.append({
                    "price": price,
                    "plans": [p.name for p in same],
                    "speeds": [speed],
                    "customer_count": Customer.objects.filter(
                        plan__in=same).count(),
                    "problem": (
                        f"PHP {price:,.0f} at {speed} Mbps is defined "
                        f"{len(same)} times ({', '.join(p.name for p in same)}). "
                        f"Two products cannot occupy the same price and speed -- "
                        f"one of them will never be sold or is a duplicate."
                    ),
                })

        speeds = {p.speed_mbps for p in group}
        if len(speeds) > 1:
            # Informational only: distinct speeds at one price. Flag it as a
            # problem only if the names do not say which speed is which.
            unnamed = [
                p for p in group
                if not any(str(s) in p.name for s in speeds if s)
            ]
            names = [p.name for p in group]
            entry = {
                "price": price,
                "plans": names,
                "speeds": sorted(s for s in speeds if s is not None),
                "customer_count": Customer.objects.filter(
                    plan__in=group).count(),
                "problem": (
                    f"PHP {price:,.0f} is sold at "
                    f"{len(speeds)} different speeds. Every plan name states its "
                    f"own speed, so a subscriber is never ambiguous."
                ),
            }
            variants.append(entry)
            if len(unnamed) > 1:
                ambiguous.append({
                    **entry,
                    "problem": (
                        f"PHP {price:,.0f} is sold at "
                        f"{len(speeds)} different speeds, and "
                        f"{len(unnamed)} of those plans do not state the speed in "
                        f"their name ({', '.join(p.name for p in unnamed)}). "
                        f"The import cannot tell them apart."
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
        "variants": variants,
        "unmapped": unmapped,
        "total_plans": len(plans),
        "plans_with_profile": len(plans) - len(unmapped),
        "top_plans_by_customers": usage,
        "clean": not ambiguous and not unmapped,
    }


def health_summary_line():
    h = plan_health()
    if h["clean"]:
        extra = ""
        if h.get("variants"):
            extra = (f" ({len(h['variants'])} price tier(s) sold at more than one "
                     f"speed, each named for its own speed)")
        return (f"Plan health: OK - all {h['total_plans']} plans have a router "
                f"profile and none is ambiguous{extra}.")
    parts = []
    if h["ambiguous"]:
        parts.append(f"{len(h['ambiguous'])} ambiguous or duplicated plan(s)")
    if h["unmapped"]:
        parts.append(f"{len(h['unmapped'])} plan(s) with no router profile")
    return "Plan health: " + ", ".join(parts) + "."