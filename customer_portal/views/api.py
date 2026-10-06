from django.http import JsonResponse
from django.utils import timezone
from billing.models import Customer
from network_manager.services import MikrotikAPI
import re
import logging

logger = logging.getLogger(__name__)


def portal_router_uplink_api(request):
    customer_id = request.session.get("customer_id")
    if not customer_id:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Customer not found"}, status=404)

    if not customer.mikrotik_device:
        return JsonResponse({"status": "error", "message": "No router assigned"})

    device = customer.mikrotik_device
    try:
        api = MikrotikAPI(device)
        api_conn = api._get_api()
        resource_data = api_conn.get_resource("/system/resource").get()[0]

        # THREE outcomes, not two.
        #
        # This used to default to "Offline" and swallow every exception, so
        # whenever the ping could not run -- ROUTER_MODE=read_only blocked the
        # call, the socket timed out, the router was mid-reboot -- the portal
        # reported a customer with working internet as "Offline" and still
        # answered 200 "success". A subscriber is told their line is down when
        # the only truth is that we could not check. "Unknown" is honest, and
        # the portal UI already has a neutral state for it.
        uplink_status = "Unknown"
        uplink_ping = None
        uplink_note = ""
        try:
            ping_res = api_conn.get_resource("/").call("ping", {"address": "8.8.8.8", "count": "1"})
            if ping_res and len(ping_res) > 0:
                result = ping_res[0]
                loss = int(result.get("packet-loss", 100))
                if loss == 100 or result.get("status") in ("no route to host", "timeout"):
                    uplink_status = "Offline"
                    uplink_ping = "Timeout"
                else:
                    avg_rtt_str = result.get("avg-rtt", "0ms")
                    match = re.search(r"([\d.]+)", str(avg_rtt_str))
                    rtt_val = float(match.group(1)) if match else 0.0
                    uplink_ping = f"{int(rtt_val)}ms"
                    uplink_status = "Unstable" if rtt_val > 150 else "Online"
        except Exception as exc:
            uplink_note = (
                "Could not check the connection right now (%s). This does not "
                "mean your internet is down." % type(exc).__name__
            )
            logger.info("portal uplink check failed for %s: %s",
                        customer.pppoe_username, exc)

        health_data = []
        try:
            health_data = api_conn.get_resource("/system/health").get()
        except Exception:
            pass

        api.connection.disconnect()
        optical_data = api.get_optical_readings()

        return JsonResponse({
            "status": "success",
            "resource": resource_data,
            "health": health_data,
            "optical": optical_data,
            "uplink_status": uplink_status,
            "uplink_ping": uplink_ping,
            # So the UI can say "we could not check" instead of leaving a
            # subscriber staring at a bare "Unknown".
            "uplink_note": uplink_note,
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})
