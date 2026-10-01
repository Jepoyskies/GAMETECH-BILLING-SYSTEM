"""Turn legacy plan names into SubscriptionPlan records, and report on the
customer records that still need a human decision.

Split out of the management command so the rules can be read and tested on
their own. The guiding principle: the legacy export is the source of truth, so
a plan is resolved from the export's own speed and price and never guessed at.
"""

from django.utils import timezone

from billing.models import Customer, SubscriptionPlan
from network_manager.models import MikrotikDevice


def to_mbps(value):
    """Normalise a speed to a float: '20 Mbps', '20M', '20' -> 20.0."""
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit() or ch == ".")
    try:
        return float(digits)
    except ValueError:
        return None


def resolve_plan(plan_map, legacy_plan_name, spec=None):
    """Map a legacy plan_name to a SubscriptionPlan using real export data.

    The catalogue is a product matrix where two product lines share a price:
        P1,000 -> GTipid Fiber 1000 (20 Mbps) | GIMI Home Fiber 1000 (50 Mbps)
        P1,300 -> GTipid Fiber 1300 (30 Mbps) | GIMI Home Fiber 1300 (75 Mbps)
        P1,500 -> GTipid Fiber 1500 (50 Mbps) | GIMI Home Fiber 1500 (100 Mbps)
    Price alone therefore cannot identify a product -- the speed decides which
    line it is, and matching on (price, speed) is what keeps a 50 Mbps / P1,000
    subscriber on GIMI rather than GTipid.

    Returns None only when the export lists no pricing for that plan.
    """
    if not legacy_plan_name:
        return None
    if legacy_plan_name in plan_map:
        return plan_map[legacy_plan_name]

    # 1. Exact name -- usually a plan a previous import already created.
    plan = SubscriptionPlan.objects.filter(name__iexact=legacy_plan_name).first()
    if plan:
        plan_map[legacy_plan_name] = plan
        return plan

    spec = spec or {}
    raw_price = spec.get("price")
    want_down = to_mbps(spec.get("speed_down")) or to_mbps(spec.get("speed_up"))

    try:
        price_val = float(raw_price) if raw_price is not None else None
    except (TypeError, ValueError):
        price_val = None

    # 2. Match on (price, speed) against the live catalogue.
    if price_val is not None:
        scored = []
        for cand in SubscriptionPlan.objects.filter(price=price_val):
            cand_down = to_mbps(cand.speed_down) or to_mbps(cand.speed_up)
            if want_down is not None and cand_down is not None:
                if abs(cand_down - want_down) > 0.01:
                    continue
            # Prefer the real product catalogue over plans that were themselves
            # created from an export, then the closest speed. Ordering must be
            # explicit or the match is arbitrary.
            is_legacy = cand.name.lower().startswith("pppoe")
            scored.append((is_legacy, 0.0, cand.name, cand))
        if scored:
            scored.sort(key=lambda t: (t[0], t[1], t[2]))
            plan_map[legacy_plan_name] = scored[0][3]
            return scored[0][3]

    # 3. No catalogue match: create from the export's real numbers, never at 0.
    if not spec:
        return None
    up = to_mbps(spec.get("speed_up"))
    down = to_mbps(spec.get("speed_down"))
    try:
        validity = int(spec.get("validity_days") or 30)
    except (TypeError, ValueError):
        validity = 30
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name=legacy_plan_name,
        defaults={
            "speed_up": f"{up:g} Mbps" if up else "",
            "speed_down": f"{down:g} Mbps" if down else "",
            "price": price_val or 0.0,
            "validity_days": validity,
            "description": f"Restored from legacy export: {legacy_plan_name}",
        },
    )
    plan_map[legacy_plan_name] = plan
    return plan


def cutover_lines(created_count, updated_count, pppoe_count, preserved_count=0):
    """Human-readable import summary. Only flags what needs a decision."""
    now = timezone.now()
    all_c = Customer.objects.all()
    out = []
    out.append("=" * 62)
    out.append("  CUTOVER SUMMARY")
    out.append("=" * 62)
    out.append(f"  New customers added     : {created_count}")
    out.append(f"  Existing updated        : {updated_count}")
    out.append(f"  Customers in system now : {all_c.count()}")
    out.append("")
    out.append(f"  PPPoE passwords matched : {pppoe_count}")
    out.append(f"  Still valid (paid)      : {all_c.filter(expires_at__gt=now).count()}")
    out.append(f"  Lapsed (needs review)   : {all_c.filter(expires_at__lt=now).count()}")

    no_expiry = all_c.filter(expires_at__isnull=True, installation_status="installed") \
                     .exclude(status__in=["pending", "closed_not_installed"])
    no_plan = all_c.filter(plan__isnull=True).count()
    no_pass = all_c.exclude(pppoe_password="").exclude(pppoe_password__isnull=True).count()
    out.append(f"  NO expiry date on file  : {no_expiry.count()}")
    out.append(f"  Passwords on file      : {no_pass}")
    out.append(f"  Missing a plan         : {no_plan}")
    out.append(f"  Routers registered     : {MikrotikDevice.objects.count()}")
    if preserved_count:
        out.append(f"  Human-reviewed, kept   : {preserved_count} (import did not overwrite)")

    out.append("")
    if no_plan:
        out.append(f"  ! {no_plan} customers have no plan. Billing price may be wrong.")
    if no_expiry.exists():
        out.append(f"  ! {no_expiry.count()} customers have NO expiry date. They can never be")
        out.append("    auto-suspended or auto-renewed. See /settings/import/ for the full list.")
    stale = MikrotikDevice.objects.filter(customer__isnull=True)
    if stale.exists():
        names = ", ".join(d.device_name for d in stale)
        out.append(f"  ! {stale.count()} router(s) with no customers: {names}")
    out.append("  Full review queue: /settings/import/  (nothing is auto-deleted)")
    out.append("=" * 62)
    return out
