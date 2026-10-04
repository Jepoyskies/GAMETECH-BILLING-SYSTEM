"""
One-off: backfill SubscriptionPlan.speed_mbps and router_profile from the
existing plan names, using the legacy export's own naming.

The legacy system (and the MikroTik profiles) name plans `pppoe-<speed>`:
  pppoe-15m_500  -> 15 Mbps, PHP 500
  pppoe-20m      -> 20 Mbps
  pppoe-50m_1200 -> 50 Mbps, PHP 1200
  pppoe-100m_1k  -> 100 Mbps, PHP 1000

Anything already named like a router profile is treated as one. Business names
("GTipid Fiber 1000") get their speed parsed out of speed_down where possible.
Safe to re-run: it only fills blanks.
"""
import re

from billing.models import SubscriptionPlan


def parse_speed(text):
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m\s*bps|mbps|m)\b", str(text), re.I)
    if m:
        try:
            return int(float(m.group(1)))
        except Exception:
            return None
    m = re.search(r"(\d{2,4})\s*m(?:_|\b)", str(text), re.I)   # pppoe-100m_1k
    if m:
        return int(m.group(1))
    return None


def go():
    print(f"{'plan':30} {'price':>9}  {'speed_mbps':>10}  router_profile")
    print("-" * 90)
    filled_speed = filled_profile = 0
    for p in SubscriptionPlan.objects.all().order_by("price"):
        spd = p.speed_mbps or parse_speed(p.name) or parse_speed(p.speed_down) \
            or parse_speed(p.speed_up)
        prof = (p.router_profile or "").strip()

        # A name that already looks like a router profile IS the profile.
        if not prof and re.match(r"^pppoe[-_]", p.name.strip(), re.I):
            prof = p.name.strip()

        changed = []
        if spd is not None and p.speed_mbps != spd:
            p.speed_mbps = spd
            changed.append("speed_mbps")
            filled_speed += 1
        if prof and p.router_profile != prof:
            p.router_profile = prof
            changed.append("router_profile")
            filled_profile += 1
        if changed:
            p.save(update_fields=changed)

        print(f"{p.name:30} {p.price:>9} {str(p.speed_mbps or ''):>10}  "
              f"{p.router_profile or '-'}")

    print("-" * 90)
    print(f"filled speed_mbps on {filled_speed} plan(s); "
          f"set router_profile on {filled_profile} plan(s)")