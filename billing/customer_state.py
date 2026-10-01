"""ONE definition of "what state is this subscriber in?", used by every screen.

Why this module exists
----------------------
The customers page used to compute "Paid but Offline" by comparing
`pppoe_username` against the `active_pppoe_usernames_set` cache. When the
routers are unreachable that cache is EMPTY, so every paid subscriber was
reported as "offline" -- 1,240 false alarms at once, on a day when not one
router could be reached. Staff would have been told to dispatch 1,240
technicians for customers who were all perfectly fine.

The fix is the same idea as `billing/diagnostics.py`: if we cannot see the
network, we say UNKNOWN and never claim "offline". Connectivity is a
measurement, and an unmeasured thing is not a fault.

Three independent domains (AGENTS.md rule 35), never collapsed:
    1. BILLING      -- paid / expiring / lapsed / no-expiry-date
    2. HARDWARE     -- the customer's PPPoE session: up / down / unknown
    3. INSTALLATION -- installed / awaiting technician

The headline `lifecycle` is the ONE word staff act on, chosen so that the
billing and hardware axes stay legible:

    Connected & Paid      -- good, leave it alone
    Connected but Unpaid  -- THE MISSING STATE. Lapsed on paper but still
                             online. This is what the old PHP system could
                             not represent, so those customers were invisible.
                             Now they are the top-priority collections queue.
    Paid but Offline      -- an outage. Real, actionable, dispatch a tech.
    Lapsed & Offline      -- churn, no action needed.
    Pending Install       -- not a subscriber yet.
    Unknown               -- we are blind. Never dispatch on this.
"""

from dataclasses import dataclass

from django.core.cache import cache
from django.utils import timezone

# A router that has not answered within this many seconds is treated as
# unreachable for connectivity purposes. Matches diagnostics.BRIDGE_STALE_SECONDS.
STALE_SECONDS = 300


@dataclass(frozen=True)
class Lifecycle:
    """One subscriber's resolved state across all three domains."""

    key: str            # machine key, e.g. "connected_unpaid"
    label: str          # what staff read
    tone: str           # bootstrap-ish token: success|warning|danger|info|neutral|unknown
    billing: str        # paid | expiring | lapsed | no_expiry | pending
    hardware: str       # connected | offline | unknown | none
    actionable: bool    # should a human do something about this row right now?
    priority: int       # 0 = most urgent. Drives list ordering.
    hint: str           # plain-English "what does this mean" for the tooltip


# --- The vocabulary. One row per state staff can see. ----------------------
# Ordered by priority, most urgent first.
LIFECYCLES = {
    "connected_unpaid": Lifecycle(
        key="connected_unpaid",
        label="Connected, Unpaid",
        tone="warning",
        billing="lapsed",
        hardware="connected",
        actionable=True,
        priority=0,
        hint="Expired on paper but still online. Collect payment -- do NOT "
             "suspend automatically.",
    ),
    "paid_offline": Lifecycle(
        key="paid_offline",
        label="Paid, Offline",
        tone="danger",
        billing="paid",
        hardware="offline",
        actionable=True,
        priority=1,
        hint="Paid and active but has no session. Real outage -- dispatch.",
    ),
    "expiring": Lifecycle(
        key="expiring",
        label="Expiring",
        tone="warning",
        billing="expiring",
        hardware="connected",
        actionable=True,
        priority=2,
        hint="Paid, online, and expires within 7 days. Send a renewal reminder.",
    ),
    "no_expiry": Lifecycle(
        key="no_expiry",
        label="No Expiry Date",
        tone="warning",
        billing="no_expiry",
        hardware="unknown",
        actionable=True,
        priority=3,
        hint="Installed line with no expiry date. Billing cannot renew or "
             "suspend it until a human sets a date.",
    ),
    "pending_install": Lifecycle(
        key="pending_install",
        label="Pending Install",
        tone="info",
        billing="pending",
        hardware="none",
        actionable=True,
        priority=4,
        hint="Applied but not installed yet. Awaiting technician.",
    ),
    "connected_paid": Lifecycle(
        key="connected_paid",
        label="Connected, Paid",
        tone="success",
        billing="paid",
        hardware="connected",
        actionable=False,
        priority=5,
        hint="Healthy. Online and paid up.",
    ),
    "paid_unknown": Lifecycle(
        key="paid_unknown",
        label="Paid, Status Unknown",
        tone="neutral",
        billing="paid",
        hardware="unknown",
        actionable=False,
        priority=6,
        hint="Paid and fine on paper, but we cannot currently see the router. "
             "Do NOT dispatch -- we are blind, not the customer.",
    ),
    "lapsed_offline": Lifecycle(
        key="lapsed_offline",
        label="Lapsed, Offline",
        tone="neutral",
        billing="lapsed",
        hardware="offline",
        actionable=False,
        priority=7,
        hint="Past due and already disconnected. Normal churn.",
    ),
    "suspended": Lifecycle(
        key="suspended",
        label="Suspended",
        tone="warning",
        billing="lapsed",
        hardware="offline",
        actionable=False,
        priority=8,
        hint="Manually locked off. Reconnect on payment.",
    ),
    "pulled_out": Lifecycle(
        key="pulled_out",
        label="Pulled Out",
        tone="neutral",
        billing="lapsed",
        hardware="offline",
        actionable=False,
        priority=9,
        hint="Line removed by technician. Not a subscriber.",
    ),
    "inactive": Lifecycle(
        key="inactive",
        label="Inactive",
        tone="neutral",
        billing="lapsed",
        hardware="offline",
        actionable=False,
        priority=10,
        hint="Decommissioned or churned.",
    ),
    "unclassified": Lifecycle(
        key="unclassified",
        label="Unclassified",
        tone="unknown",
        billing="unknown",
        hardware="unknown",
        actionable=False,
        priority=11,
        hint="State could not be determined.",
    ),
}

# The filter pills, in display order. Each maps to exactly ONE lifecycle key
# except "all", so the pills are mutually exclusive and sum to the total.
FILTERS = [
    ("connected_unpaid", "Connected, Unpaid", "fa-plug-circle-exclamation", "warning"),
    ("paid_offline", "Paid but Offline", "fa-triangle-exclamation", "danger"),
    ("expiring", "Expiring", "fa-clock", "warning"),
    ("connected_paid", "Connected, Paid", "fa-circle-check", "success"),
    ("no_expiry", "No Expiry Date", "fa-calendar-xmark", "warning"),
    ("pending_install", "Pending Install", "fa-screwdriver-wrench", "info"),
    ("lapsed_offline", "Lapsed, Offline", "fa-ban", "neutral"),
    ("pulled_out", "Pulled Out", "fa-plug-circle-xmark", "neutral"),
]


def network_visibility():
    """Are we actually able to see the routers right now?

    Returns (visible: bool, connected_usernames: set[str] | None).

    `connected_usernames` is None when we are blind, and that None is
    load-bearing: it is what stops the customers page from reporting every
    paid subscriber as "offline" just because the poll came back empty.
    """
    from billing.diagnostics import get_bridge_status

    bridge = get_bridge_status()
    if bridge["status"] != "Online":
        return False, None

    # Even with a healthy bridge, an empty active-user set is only meaningful
    # if we can see at least one router with a working uplink. Otherwise an
    # empty set means "we asked and got nothing", not "nobody is online".
    live = cache.get("live_monitoring_data") or {}
    routers = live.get("routers") or []
    if not any(r.get("internet_online") for r in routers):
        return False, None

    active = cache.get("active_pppoe_usernames_set")
    if active is None:
        return False, None
    return True, {str(u).lower() for u in active if u}


def billing_state(customer, now=None):
    """The billing axis alone: paid | expiring | lapsed | no_expiry | pending."""
    now = now or timezone.now()

    if customer.installation_status == "pending" or customer.status == "pending":
        return "pending"
    if customer.status in ("pull out",):
        return "pulled_out"
    if customer.status == "inactive":
        return "inactive"
    if customer.status == "suspended":
        return "suspended"
    if customer.expires_at is None:
        return "no_expiry"

    if customer.expires_at > now:
        return "expiring" if customer.expires_at <= now + timezone.timedelta(days=7) else "paid"
    return "lapsed"


def hardware_state(customer, connected_usernames):
    """The hardware axis alone: connected | offline | unknown | none.

    `connected_usernames` of None means BLIND -- we return "unknown" and
    never "offline". This is the guard that stops a router outage from
    masquerading as 1,240 customer outages.
    """
    if not customer.pppoe_username:
        return "none"
    if connected_usernames is None:
        return "unknown"

    # A customer on a router we know is down is genuinely offline, even
    # though the global active set is blind for everyone else.
    if customer.mikrotik_device and cache.get(f"router_unreachable_{customer.mikrotik_device.id}"):
        return "offline"

    return "connected" if str(customer.pppoe_username).lower() in connected_usernames else "offline"


def resolve(customer, connected_usernames, now=None):
    """Combine both axes into exactly one Lifecycle."""
    now = now or timezone.now()
    billing = billing_state(customer, now)
    hardware = hardware_state(customer, connected_usernames)

    if billing == "pending":
        return LIFECYCLES["pending_install"]
    if billing == "pulled_out":
        return LIFECYCLES["pulled_out"]
    if billing == "inactive":
        return LIFECYCLES["inactive"]
    if billing == "suspended":
        return LIFECYCLES["suspended"]
    if billing == "no_expiry":
        return LIFECYCLES["no_expiry"]

    paid = billing in ("paid", "expiring")

    if paid and hardware == "connected":
        return LIFECYCLES["expiring"] if billing == "expiring" else LIFECYCLES["connected_paid"]
    if paid and hardware == "offline":
        return LIFECYCLES["paid_offline"]
    if paid and hardware in ("unknown", "none"):
        return LIFECYCLES["paid_unknown"]

    # Lapsed from here down.
    if hardware == "connected":
        return LIFECYCLES["connected_unpaid"]
    if hardware in ("unknown", "none"):
        # Lapsed and we cannot see them. Do NOT call it churn -- that is a
        # guess. Keep it out of the "lapsed offline" bucket.
        return LIFECYCLES["paid_unknown"]
    return LIFECYCLES["lapsed_offline"]


def annotate(queryset, connected_usernames, now=None):
    """Attach `lifecycle` to every row without an N+1 query storm.

    We resolve in Python rather than in SQL because the hardware axis depends
    on a cache set that SQL cannot see. The list page already renders every
    row client-side, so the per-row cost is a dict lookup, not a query.
    """
    now = now or timezone.now()
    rows = list(queryset)
    for row in rows:
        row.lifecycle = resolve(row, connected_usernames, now)
    return rows
