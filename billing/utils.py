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
    from network_manager.models import MikrotikDevice
    from billing.models import Customer
    from network_manager.services import MikrotikAPI

    logger = logging.getLogger(__name__)

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

            api.connection.disconnect()
        except Exception as e:
            logger.error(f"Error connecting to Mikrotik {device.device_name}: {e}")

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
