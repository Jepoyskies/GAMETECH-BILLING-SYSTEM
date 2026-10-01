"""Three-layer link diagnosis: Home Router -> MikroTik -> Mini PC.

Answers one question when a customer says "no internet": whose fault is it?

The chain, top-down:

    1. Mini PC bridge   (office PC + Tailscale tunnel the cloud polls through)
    2. MikroTik router  (does it answer, and does it have an internet uplink?)
    3. Home router      (is the customer's PPPoE session actually up?)

Every layer *below* a broken layer is meaningless, so we report the FIRST
broken link and exactly what to check. Reporting "Offline" for a customer
while our own bridge is down is a false accusation -- hence the blind check.

Why two independent signals for layer 1
---------------------------------------
The cloud reaches the routers *through* the Mini PC, so "no router answered"
cannot distinguish a dead Mini PC from a dead office uplink/repeater. So we
also have the Mini PC report in for itself, via `bridge_tunnel` (posted by
scripts/bridge_heartbeat.sh from the real Tailscale peer state):

    tunnel UP   + routers DOWN -> Mini PC is WORKING. Fault is the LAN between
                                   it and the routers (cable/switch/router).
    tunnel DOWN + routers DOWN -> our side: Mini PC off, or uplink dead.
    tunnel UP   + routers UP   -> bridge healthy, judge the router normally.

That turns "is the Mini PC working?" from a guess into a measurement.
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
        "headline": "No visibility — we cannot see the network at all",
        "action": (
            "Do NOT dispatch a technician. Nothing below the bridge can be trusted, "
            "because we cannot currently see any MikroTik."
        ),
        "check": [
            "Is the bridge heartbeat installed and running? (host cron → bridge_heartbeat.sh)",
            "Mini PC: powered on?",
            "Tailscale: connected on the Mini PC AND on the cloud server?",
            "Office internet / WiFi repeater alive?",
        ],
    },
    "bridge_down": {
        "layer": "bridge",
        "severity": "danger",
        "headline": "Mini PC bridge is OFFLINE — fault is on our side",
        "action": (
            "The Mini PC is not talking to the cloud, so no router status can be "
            "trusted. Do NOT dispatch to a customer's house."
        ),
        "check": [
            "Mini PC: powered on at all?",
            "Office internet / WiFi repeater working? (this is the usual culprit)",
            "Tailscale: run `tailscale status` on the Mini PC and check it says connected",
            "Reseat the LAN cable from the Mini PC into the switch/router port",
        ],
    },
    "bridge_lan": {
        "layer": "bridge",
        "severity": "danger",
        "headline": "Mini PC is WORKING, but cannot see any router — fault is the LAN to them",
        "action": (
            "The bridge is healthy and online, yet not a single MikroTik answered. "
            "The break is between the Mini PC and the routers. Do NOT dispatch."
        ),
        "check": [
            "LAN cable from the switch to the MikroTik WAN port — reseat both ends",
            "MikroTik power LEDs — is any router actually powered on?",
            "Try a different switch port (bad ports are a known repeat offender)",
            "Has a router's LAN IP changed? Verify each device's ip_address",
        ],
    },
    "router_unreachable": {
        "layer": "router",
        "severity": "danger",
        "headline": "This MikroTik is unreachable — other routers are fine",
        "action": (
            "The bridge is healthy and other routers answered, so the break is "
            "specific to this router. Not a customer problem — do not dispatch."
        ),
        "check": [
            "LAN cable from the switch to THIS router's port — reseat both ends",
            "Is this router powered on? Check its power LED",
            "Try a different switch port (bad ports are a known repeat offender)",
            "Has this router's LAN IP changed? Verify the device's ip_address",
        ],
    },
    "no_uplink": {
        "layer": "router",
        "severity": "danger",
        "headline": "MikroTik answers but has NO internet — fault is upstream of it",
        "action": (
            "The router is reachable but cannot reach 8.8.8.8. This is a WAN/uplink "
            "problem, not a customer problem."
        ),
        "check": [
            "MikroTik WAN interface: is the upstream fiber/DSL link up?",
            "Check the MikroTik WAN default gateway and DNS",
            "Check the OLT / upstream provider for that area",
            "Are OTHER customers on this same router down? If all of them are, it is this router",
        ],
    },
    "home_router": {
        "layer": "home",
        "severity": "warning",
        "headline": "MikroTik is healthy — the fault is between it and the customer's house",
        "action": (
            "The router has internet and is updating normally. This customer's own "
            "drop or router is at fault — safe to dispatch."
        ),
        "check": [
            "Is the PPPoE secret on the MikroTik enabled and unexpired?",
            "Which MikroTik port is the customer plugged into?",
            "Ask the customer to power-cycle their ONT/router",
            "Look for a cut drop fiber between the MikroTik and their house",
        ],
    },
    "healthy": {
        "layer": None,
        "severity": "success",
        "headline": "All three links are healthy — the line itself is fine",
        "action": (
            "Do NOT dispatch. The MikroTik has internet and this customer's session "
            "is up, so the fault is on the customer's own device."
        ),
        "check": [
            "Ask the customer to restart their router and all their devices",
            "Confirm their WiFi password / SSID",
            "Test a different device to rule out one broken machine",
            "Check DNS: have them try 8.8.8.8 manually",
        ],
    },
}


def get_bridge_status():
    """Mini PC / office bridge health.

    Prefers the MEASURED signal (`bridge_tunnel`, posted by the host cron from
    real Tailscale peer state). Falls back to inferring it from poll success
    when no heartbeat has ever arrived, so the page still works before the
    host cron is installed.
    """
    counts = cache.get("bridge_link_status") or {}
    reached, total = counts.get("reached"), counts.get("total")

    tunnel = cache.get("bridge_tunnel")
    if tunnel:
        age = int(time.time() - float(tunnel.get("received_at") or 0))
        if age > BRIDGE_STALE_SECONDS:
            # Heartbeat itself has gone quiet — the cron or the POST is broken.
            return {
                "status": "Unknown",
                "measured": True,
                "hostname": tunnel.get("hostname", ""),
                "reached": reached,
                "total": total,
                "age": age,
            }
        return {
            # Measured fact: is the Mini PC's Tailscale peer up?
            "status": "Online" if tunnel.get("online") else "Offline",
            "measured": True,
            "hostname": tunnel.get("hostname", ""),
            "reached": reached,
            "total": total,
            "age": age,
        }

    # --- Fallback: no heartbeat ever received, infer from poll success --------
    last_ok = cache.get("bridge_last_ok")
    if last_ok is None:
        return {
            "status": "Unknown",
            "measured": False,
            "hostname": "",
            "reached": reached,
            "total": total,
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
        "measured": False,
        "hostname": "",
        "reached": reached,
        "total": total,
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
    """Walk the chain top-down and return the first broken link + what to check.

    Two independent signals decide layer 1:
      * `bridge_tunnel`  — the Mini PC's own report (measured)
      * router poll      — did anything answer through it
    Together they separate "the Mini PC is broken" from "the LAN to the routers
    is broken", which a router-only signal can never do.
    """
    bridge = get_bridge_status()
    router_state, router_detail = _router_link(customer)
    home_state, home_detail = _home_link(customer)

    routers_reached = bridge.get("reached")
    routers_total = bridge.get("total")
    no_router_answered = (
        routers_reached is not None
        and routers_total is not None
        and routers_total > 0
        and routers_reached == 0
    )

    if bridge["status"] == "Offline" and bridge["measured"]:
        # MEASURED: the Mini PC itself is not talking to us.
        verdict = "bridge_down"
    elif bridge["status"] not in ("Online",):
        # Unknown / Stale / heartbeat gone quiet -> we cannot see anything.
        verdict = "blind"
    elif bridge["measured"] and no_router_answered:
        # MEASURED bridge is up, yet nothing answered -> the LAN to them is broken.
        verdict = "bridge_lan"
    elif router_state == "Unknown":
        verdict = "blind"
    elif router_state == "Unreachable":
        verdict = "router_unreachable"
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
        "bridge_measured": bridge["measured"],
        "bridge_hostname": bridge["hostname"],
        "bridge_age": bridge["age"],
        "bridge_reached": routers_reached,
        "bridge_total": routers_total,
        "router": router_state,
        "router_detail": router_detail,
        "home": home_state,
        "home_detail": home_detail,
        "verdict": verdict,
        **VERDICTS[verdict],
    }
