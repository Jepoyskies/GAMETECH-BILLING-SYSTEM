"""Three-layer link diagnosis: Home Router -> MikroTik -> Mini PC.

Answers one question when a customer says "no internet": whose fault is it?

The chain, top-down:

    1. Mini PC bridge   (office PC + Tailscale tunnel the cloud polls through)
    2. MikroTik router  (does it answer, and does it have an internet uplink?)
    3. Home router      (is the customer's PPPoE session actually up?)

Every layer *below* a broken layer is meaningless, so we report the FIRST
broken link and exactly what to check. Reporting "Offline" for a customer
while our own bridge is down is a false accusation -- hence the blind check.
"""

import time

from django.core.cache import cache

# A router answered the poll within BRIDGE_FRESH_SECONDS => we have eyes.
BRIDGE_FRESH_SECONDS = 90
# Older than that but still inside BRIDGE_STALE_SECONDS => eyes are half-open.
BRIDGE_STALE_SECONDS = 300

# Escalation ladder. First match wins, top-down.
VERDICTS = {
    "blind": {
        "layer": "bridge",
        "severity": "danger",
        "headline": "Our monitoring is blind -- this is NOT the customer's fault",
        "action": (
            "Do NOT dispatch a technician. Nothing below the bridge can be trusted, "
            "because we have not heard from any MikroTik recently."
        ),
        "check": [
            "Mini PC: is it powered on?",
            "Tailscale: is the tunnel up on the Mini PC AND on the cloud server?",
            "Office LAN: reseat the cable from the Mini PC into the switch/router port.",
            "Was there a power outage at the office?",
        ],
    },
    "bridge_path": {
        "layer": "router",
        "severity": "danger",
        "headline": "MikroTik is unreachable -- the fault is ABOVE the customer",
        "action": (
            "The customer's house is not the problem. Restore the path from the "
            "Mini PC to this router first."
        ),
        "check": [
            "Mini PC: powered on and Tailscale connected?",
            "LAN cable from the switch to the MikroTik WAN port -- reseat both ends.",
            "MikroTik power LED on?",
            "Power outage at that site?",
        ],
    },
    "no_uplink": {
        "layer": "router",
        "severity": "danger",
        "headline": "MikroTik answers but has NO internet -- fault is upstream of it",
        "action": (
            "The router is reachable but cannot reach 8.8.8.8. This is a WAN/uplink "
            "problem, not a customer problem."
        ),
        "check": [
            "MikroTik WAN interface: is the upstream fiber/DSL link up?",
            "Check the MikroTik WAN default gateway and DNS.",
            "Check the OLT / upstream provider for that area.",
            "Are OTHER customers on this same router down? If all of them are, it is this router.",
        ],
    },
    "home_router": {
        "layer": "home",
        "severity": "warning",
        "headline": "MikroTik is healthy -- the fault is between it and the customer's house",
        "action": (
            "The router has internet and is updating normally. This customer's own "
            "drop or router is at fault -- safe to dispatch."
        ),
        "check": [
            "Is the PPPoE secret on the MikroTik enabled and unexpired?",
            "Which MikroTik port is the customer plugged into?",
            "Ask the customer to power-cycle their ONT/router.",
            "Look for a cut drop fiber between the MikroTik and their house.",
        ],
    },
    "healthy": {
        "layer": None,
        "severity": "success",
        "headline": "All three links are healthy -- the line itself is fine",
        "action": (
            "Do NOT dispatch. The MikroTik has internet and this customer's session "
            "is up, so the fault is on the customer's own device."
        ),
        "check": [
            "Ask the customer to restart their router and all their devices.",
            "Confirm their WiFi password / SSID.",
            "Test a different device to rule out one broken machine.",
            "Check DNS: have them try 8.8.8.8 manually.",
        ],
    },
}


def get_bridge_status():
    """Mini PC / office bridge health, inferred from poll success.

    Every MikroTik sits behind the same Mini PC, so when *none* of them answer
    at all, the fault is upstream of all of them -- our side of the bridge.
    We write `bridge_last_ok` on every cycle that reached at least one router;
    its age is therefore "how long since we had eyes on the network".
    """
    counts = cache.get("bridge_link_status") or {}
    last_ok = cache.get("bridge_last_ok")

    if last_ok is None:
        return {
            "status": "Unknown",
            "reached": counts.get("reached"),
            "total": counts.get("total"),
            "age": None,
        }

    age = int(time.time() - float(last_ok))
    if age <= BRIDGE_FRESH_SECONDS:
        status = "Online"
    elif age <= BRIDGE_STALE_SECONDS:
        status = "Stale"
    else:
        status = "Offline"
    return {
        "status": status,
        "reached": counts.get("reached"),
        "total": counts.get("total"),
        "age": age,
    }


def _router_link(customer):
    """MikroTik layer: does it answer, and does it have an internet uplink?"""
    device = customer.mikrotik_device
    if not device:
        return "Unknown", "No router assigned"
    if cache.get(f"router_unreachable_{device.id}"):
        return "Unreachable", "Connection refused by the router"

    for r in (cache.get("live_monitoring_data") or {}).get("routers", []):
        if r.get("device_name") == device.device_name:
            if r.get("internet_online"):
                return "Online", "Reachable, with a working internet uplink"
            return "No Internet", "Reachable, but cannot reach the internet"

    return "Unreachable", "Did not answer the last poll"


def _home_link(customer):
    """Customer's own router: is the PPPoE session actually established?"""
    if not customer.pppoe_username:
        return "Unknown", "No PPPoE configured"
    active = cache.get("active_pppoe_usernames_set") or set()
    if str(customer.pppoe_username).lower() in {str(u).lower() for u in active}:
        return "Online", "PPPoE session is up"
    return "Offline", "PPPoE session is not established"


def diagnose_link(customer):
    """Walk the chain top-down and return the first broken link + what to check."""
    bridge = get_bridge_status()
    router_state, router_detail = _router_link(customer)
    home_state, home_detail = _home_link(customer)

    if bridge["status"] != "Online":
        verdict = "blind"
    elif router_state == "Unknown":
        verdict = "blind"
    elif router_state == "Unreachable":
        verdict = "bridge_path"
    elif router_state == "No Internet":
        verdict = "no_uplink"
    elif home_state == "Unknown":
        verdict = "blind"
    elif home_state == "Offline":
        verdict = "home_router"
    else:
        verdict = "healthy"

    return {
        "bridge": bridge["status"],
        "bridge_age": bridge["age"],
        "bridge_reached": bridge["reached"],
        "bridge_total": bridge["total"],
        "router": router_state,
        "router_detail": router_detail,
        "home": home_state,
        "home_detail": home_detail,
        "verdict": verdict,
        **VERDICTS[verdict],
    }
