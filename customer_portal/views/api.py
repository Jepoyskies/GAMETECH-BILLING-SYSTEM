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

        uplink_status = "Offline"
        uplink_ping = "Timeout"
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
        except Exception:
            pass

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
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})
