import json
from .models import SystemLog


def log_system_action(
    table_name,
    record_id,
    action,
    changed_by,
    target_name=None,
    old_data=None,
    new_data=None,
):
    """
    Helper function to record an audit log in the SystemLog model.
    old_data and new_data should be dicts, which will be stored as JSON text.
    """
    old_json = json.dumps(old_data) if old_data else None
    new_json = json.dumps(new_data) if new_data else None

    SystemLog.objects.create(
        table_name=table_name,
        record_id=str(record_id),
        action=action,
        changed_by=changed_by,
        target_name=target_name,
        old_data=old_json,
        new_data=new_json,
    )


def get_live_monitoring_data_sync():
    import logging
    import time
    from django.core.cache import cache
    from network_manager.models import MikrotikDevice
    from billing.models import Customer
    from network_manager.services import MikrotikAPI

    logger = logging.getLogger(__name__)

    # Every connected PPPoE name across every router that answered.
    all_connected = set()

    response_data = {
        "users": [],
        "routers": [],
        "offline_users": [],
        "total_active_subs": 0,
    }

    # Build lookup map of PPPoE username -> customer metadata
    customer_map = {}
    for c in (
        Customer.objects.exclude(pppoe_username__isnull=True)
        .exclude(pppoe_username="")
        .values("id", "full_name", "pppoe_username")
    ):
        raw_user = c["pppoe_username"]
        info = {"id": c["id"], "full_name": c["full_name"]}
        customer_map[raw_user] = info
        if raw_user.lower() not in customer_map:
            customer_map[raw_user.lower()] = info

    devices = MikrotikDevice.objects.all()
    for device in devices:
        # Skip a router the circuit breaker has already written off.
        #
        # Three of the four routers are currently unreachable. Each one costs a
        # full socket timeout per cycle, which is what stretched this task from
        # its intended 10 seconds to a measured 178-221s -- and with a 30s cache
        # TTL that meant the customer list read an EMPTY cache about 150 seconds
        # out of every 180, so every subscriber rendered "Unknown". The breaker
        # already knows; do not pay for the socket again.
        if cache.get(f"router_unreachable_{device.id}"):
            logger.warning(
                "Skipping %s in the live poll: circuit breaker has it marked "
                "unreachable.", device.device_name,
            )
            continue
        try:
            api = MikrotikAPI(device)
            active_users = api.get_active_pppoe_users()

            # Fetch active customers from DB
            active_db_customers = (
                Customer.objects.filter(status="active", mikrotik_device=device)
                .exclude(pppoe_username__isnull=True)
                .exclude(pppoe_username="")
            )

            response_data["total_active_subs"] += active_db_customers.count()

            # Fetch traffic for all active PPPoE users directly from their dynamic interfaces
            interface_names = [
                f"<pppoe-{au.get('name')}>" for au in active_users if au.get("name")
            ]
            traffic_data = api.get_interfaces_traffic(interface_names)

            # Map traffic data by clean username
            traffic_dict = {}
            for t in traffic_data:
                name = t.get("name", "")
                # Strip `<pppoe-` prefix and `>` suffix
                clean_name = name.strip("<>").replace("pppoe-", "", 1)

                try:
                    rx_bps = int(t.get("rx-bits-per-second", 0))
                    tx_bps = int(t.get("tx-bits-per-second", 0))
                    rx_mbps = round(rx_bps / 1000000, 2)
                    tx_mbps = round(tx_bps / 1000000, 2)
                    traffic_dict[clean_name] = {"rx_mbps": rx_mbps, "tx_mbps": tx_mbps}
                except Exception:
                    continue

            for au in active_users:
                username = au.get("name")
                if username:
                    # THIS IS THE FIX. The customer list resolves every
                    # customer's Online/Offline badge by comparing
                    # pppoe_username against the `active_pppoe_usernames_set`
                    # cache -- and that key was only ever written by the
                    # network API view, i.e. when a human happened to open Live
                    # Monitoring. The background poll collects exactly this
                    # information and discarded it, so the customers page
                    # rendered "Unknown" for all 2,038 accounts unless someone
                    # was looking at the live dashboard at that moment.
                    all_connected.add(str(username).lower())
                tr = traffic_dict.get(username, {"rx_mbps": 0.0, "tx_mbps": 0.0})
                cust_match = customer_map.get(username) or (
                    customer_map.get(username.lower()) if username else None
                )
                customer_name = (
                    cust_match["full_name"].strip()
                    if (cust_match and cust_match.get("full_name"))
                    else username
                )
                customer_id = cust_match["id"] if cust_match else None
                response_data["users"].append(
                    {
                        "user": username,
                        "customer_name": customer_name,
                        "customer_id": customer_id,
                        "ip": au.get("address", ""),
                        "uptime": au.get("uptime", "0s"),
                        "rx_mbps": tr["rx_mbps"],
                        "tx_mbps": tr["tx_mbps"],
                        "device_ip": device.ip_address,
                    }
                )

            # Determine if router has internet uplink by pinging 8.8.8.8
            internet_online = False
            try:
                ping_res = (
                    api._get_api()
                    .get_resource("/")
                    .call("ping", {"address": "8.8.8.8", "count": "2"})
                )
                if ping_res and len(ping_res) > 0:
                    successful = [
                        p for p in ping_res
                        if str(p.get("packet-loss", "100")) != "100"
                        and "avg-rtt" in p
                    ]
                    internet_online = len(successful) > 0
            except Exception:
                pass

            response_data["routers"].append({
                "device_name": device.device_name,
                "ip_address": device.ip_address,
                "internet_online": internet_online,
                "active_users": len(active_users),
            })

            api.connection.disconnect()
        except Exception as e:
            logger.error(f"Error connecting to Mikrotik {device.device_name}: {e}")

    # --- Mini PC bridge health -----------------------------------------------
    # We poll the routers THROUGH the office Mini PC (Tailscale subnet router).
    # A router only lands in `routers` if it actually answered, so if none of
    # them did, the fault is upstream of all of them: our bridge. Recording this
    # lets the UI say "we are blind" instead of accusing every subscriber.
    cache.set(
        "bridge_link_status",
        {"reached": len(response_data["routers"]), "total": devices.count()},
        300,
    )
    if response_data["routers"]:
        # Only refreshed on success, so its age = "time since we had eyes".
        cache.set("bridge_last_ok", time.time(), 600)

    # The TTL has to outlast the WORST-CASE cycle, not the ideal one.
    #
    # This task is scheduled every 10s but measured at 178-221s whenever any
    # router is slow, so a 30s TTL expired between nearly every poll and the
    # customers page saw "we are blind" for most of each cycle. 300s gives
    # ample headroom: a stale-but-real reading is far better for staff than a
    # missing one, and customer_state.network_visibility() still refuses to
    # guess when NO router answered, so a genuine outage cannot be masked.
    cache.set("active_pppoe_usernames_set", all_connected, 300)
    logger.info(
        "Live poll finished: %d router(s) answered, %d connected session(s).",
        len(response_data["routers"]), len(all_connected),
    )

    return response_data


def get_customer_base_expiration(customer):
    """
    Returns the base/Month 1 expiration date for a customer if all advance payments are reverted.
    - For new or single-cycle accounts: earliest payment's expires_at (Month 1).
    - For active recurring accounts: earliest payment covering the active cycle.
    - Fallback: customer.expires_at.
    """
    payments = customer.payments.all().order_by("paid_at", "id")
    if not payments.exists():
        if customer.expires_at:
            return customer.expires_at
        from datetime import timedelta
        return (customer.created_at or customer.id) + timedelta(days=30)

    from django.utils import timezone
    now = timezone.now()

    active_payments = payments.filter(expires_at__gte=now)
    if active_payments.exists():
        return active_payments.first().expires_at

    first_p = payments.first()
    return first_p.expires_at if first_p.expires_at else customer.expires_at
