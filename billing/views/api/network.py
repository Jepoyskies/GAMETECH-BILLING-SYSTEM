from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
    permission_required,
)
from django.views.decorators.http import require_POST
from billing.decorators import role_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, Max
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime
from billing.models import (
    SystemAdmin,
    SubscriptionPlan,
    Agent,
    AccountType,
    Customer,
    Barangay,
    Payment,
    Rebate,
    SystemLog,
    SmsLog,
    CignalPlay,
    AuditLog,
    AddOnRequest,
    Notification,
    ImprovementRequest,
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar


@login_required
def mikrotik_active_users_data_api(request):
    devices = MikrotikDevice.objects.all()
    all_active_users = []

    for device in devices:
        try:
            api = MikrotikAPI(device)
            users = api.get_active_pppoe_users()
            for u in users:
                # Append device info so we know which router they are on
                u["router_name"] = device.device_name
                u["router_ip"] = device.ip_address
                all_active_users.append(u)
        except Exception as e:
            # e is caught and used in the f-string
            messages.warning(request, f"Could not connect to {device.device_name}: {e}")

    context = {"active_users": all_active_users, "total_active": len(all_active_users)}
    return render(request, "billing/partials/active_users_table.html", context)


@login_required
def api_offline_users(request):
    response_data = {"offline_users": []}
    from billing.models import Customer

    devices = MikrotikDevice.objects.all()
    for device in devices:
        try:
            api = MikrotikAPI(device)
            active_users = api.get_active_pppoe_users()
            active_mt_usernames = {
                au.get("name") for au in active_users if au.get("name")
            }

            active_db_customers = (
                Customer.objects.filter(status="active", mikrotik_device=device)
                .exclude(pppoe_username__isnull=True)
                .exclude(pppoe_username="")
            )

            offline_customer_usernames = [
                c.pppoe_username
                for c in active_db_customers
                if c.pppoe_username not in active_mt_usernames
            ]

            if offline_customer_usernames:
                secrets = api.get_ppp_secrets()
                secrets_dict = {
                    s.get("name"): s.get("last-logged-out", "Unknown")
                    for s in secrets
                    if s.get("name")
                }

                for c in active_db_customers:
                    if c.pppoe_username in offline_customer_usernames:
                        response_data["offline_users"].append(
                            {
                                "id": c.id,
                                "full_name": c.full_name,
                                "username": c.pppoe_username,
                                "phone": c.phone,
                                "address": c.address,
                                "device_id": device.id,
                                "device_name": device.device_name,
                                "last_logged_out": secrets_dict.get(
                                    c.pppoe_username, "Unknown"
                                ),
                            }
                        )
            api.connection.disconnect()
        except Exception as e:
            print(f"Error fetching offline users for {device.device_name}: {e}")

    return JsonResponse(response_data)


@login_required
def api_router_uplink(request):
    routers = []
    devices = MikrotikDevice.objects.all()
    for device in devices:
        try:
            api = MikrotikAPI(device)
            uplink_status = "Offline"
            uplink_ping = "Timeout"
            try:
                ping_res = (
                    api._get_api()
                    .get_resource("/")
                    .call("ping", {"address": "8.8.8.8", "count": "1"})
                )
                if ping_res and len(ping_res) > 0:
                    result = ping_res[0]
                    loss = int(result.get("packet-loss", 100))
                    if (
                        loss == 100
                        or result.get("status") == "no route to host"
                        or result.get("status") == "timeout"
                    ):
                        uplink_status = "Offline"
                        uplink_ping = "Timeout"
                    else:
                        avg_rtt_str = result.get("avg-rtt", "0ms")
                        rtt_ms = int(avg_rtt_str.replace("ms", ""))
                        uplink_ping = f"{rtt_ms}ms"
                        uplink_status = "Unstable" if rtt_ms > 150 else "Online"
            except Exception as e:
                uplink_status = "Offline"
                uplink_ping = "Error"

            routers.append(
                {
                    "id": device.id,
                    "name": device.device_name,
                    "uplink_status": uplink_status,
                    "uplink_ping": uplink_ping,
                }
            )
            api.connection.disconnect()
        except Exception as e:
            # Device unreachable or API error
            pass

    return JsonResponse({"routers": routers})


@login_required
def api_customer_mikrotik_status(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    data = {
        "mt_status": "Disconnected",
        "uptime": "N/A",
        "live_mac": customer.mac_address if customer.mac_address else "N/A",
        "last_logged_out": "N/A",
    }

    if customer.mikrotik_device and customer.pppoe_username:
        try:
            from network_manager.services import MikrotikAPI

            api = MikrotikAPI(customer.mikrotik_device)

            # Fetch active users
            active_users = api.get_active_pppoe_users()
            for au in active_users:
                if au.get("name") == customer.pppoe_username:
                    data["mt_status"] = "Connected"

                    uptime_str = au.get("uptime", "N/A")
                    data["uptime"] = uptime_str
                    data["live_mac"] = au.get("caller-id", "N/A")

                    if "w" in uptime_str:
                        data["stability"] = "Excellent"
                        data["stability_color"] = "success"
                    elif "d" in uptime_str:
                        data["stability"] = "Good"
                        data["stability_color"] = "primary"
                    elif "h" in uptime_str:
                        data["stability"] = "Fine"
                        data["stability_color"] = "info"
                    elif "m" in uptime_str or "s" in uptime_str:
                        data["stability"] = "Unstable / Recent"
                        data["stability_color"] = "warning"
                    else:
                        data["stability"] = ""
                        data["stability_color"] = ""

                    # Fetch bandwidth from cache to avoid blocking
                    from django.core.cache import cache

                    live_data = cache.get("live_monitoring_data")
                    data["rx_mbps"] = 0.0
                    data["tx_mbps"] = 0.0
                    if live_data and "users" in live_data:
                        for user_data in live_data["users"]:
                            if user_data.get("user") == customer.pppoe_username:
                                data["rx_mbps"] = user_data.get("rx_mbps", 0.0)
                                data["tx_mbps"] = user_data.get("tx_mbps", 0.0)
                                break
                    break

            # Fetch secrets to get last-logged-out if disconnected
            secrets = api.get_ppp_secrets()
            for secret in secrets:
                if secret.get("name") == customer.pppoe_username:
                    data["last_logged_out"] = secret.get("last-logged-out", "N/A")
                    if data["mt_status"] == "Disconnected" and not customer.mac_address:
                        data["live_mac"] = secret.get("caller-id", "N/A")
                    break

            if getattr(api, "_connection_failed", False):
                data["mt_status"] = "API Unreachable"
            else:
                # If the customer is completely disconnected, check if the ENTIRE router is offline (lost uplink)
                if data["mt_status"] == "Disconnected":
                    try:
                        ping_res = (
                            api._get_api()
                            .get_resource("/")
                            .call("ping", {"address": "8.8.8.8", "count": "1"})
                        )
                        if ping_res and len(ping_res) > 0:
                            result = ping_res[0]
                            loss = int(result.get("packet-loss", 100))
                            if loss == 100 or result.get("status") in [
                                "no route to host",
                                "timeout",
                            ]:
                                data["mt_status"] = "Offline (Router Off)"
                    except Exception:
                        pass  # Ignore ping errors, just leave as Disconnected

        except Exception:
            data["mt_status"] = "API Unreachable"

    # Add context to disconnected status if it wasn't caught by the ping check
    if data["mt_status"] == "Disconnected":
        if customer.status == "active":
            if customer.barangay and customer.barangay.health_status == "Outage":
                data["mt_status"] = "Area Outage (Barangay)"
            elif (
                customer.mikrotik_device
                and customer.mikrotik_device.health_status == "Outage"
            ):
                data["mt_status"] = "Network Outage (Router)"
            elif customer.health_status == "Outage":
                data["mt_status"] = "Service Outage"
            else:
                data["mt_status"] = "Disconnected (Inactive)"
        elif customer.status == "suspended":
            data["mt_status"] = "Suspended"
        else:
            data["mt_status"] = f"Disconnected ({customer.get_status_display()})"

    from django.http import JsonResponse

    return JsonResponse(data)


def api_network_alerts(request):
    from billing.models import Barangay, Customer
    from network_manager.models import MikrotikDevice

    active_device_alerts = MikrotikDevice.objects.exclude(health_status="Excellent")
    active_barangay_alerts = Barangay.objects.exclude(health_status="Excellent")
    active_customer_alerts = Customer.objects.exclude(
        health_status__in=["Excellent", "Good", "Stable", "Strong"]
    ).filter(status="active")

    data = []
    for d in active_device_alerts:
        data.append(
            {
                "type": "device",
                "id": d.id,
                "name": d.device_name + " (Router)",
                "status": d.health_status,
                "reason": d.health_reason,
            }
        )
    for b in active_barangay_alerts:
        data.append(
            {
                "type": "barangay",
                "id": b.id,
                "name": b.name + " (Barangay)",
                "status": b.health_status,
                "reason": b.health_reason,
            }
        )
    for c in active_customer_alerts:
        data.append(
            {
                "type": "customer",
                "id": c.id,
                "name": c.full_name + " (Customer)",
                "status": c.health_status,
                "reason": c.health_reason,
            }
        )

    return JsonResponse({"status": "success", "alerts": data})


def api_active_pppoe_usernames(request):
    from network_manager.models import MikrotikDevice
    from network_manager.services import MikrotikAPI
    from django.http import JsonResponse

    devices = MikrotikDevice.objects.all()
    active_usernames = set()
    offline_routers = []

    for device in devices:
        try:
            api = MikrotikAPI(device)
            active_users = api.get_active_pppoe_users()
            for au in active_users:
                if au.get("name"):
                    active_usernames.add(au.get("name"))
        except Exception:
            offline_routers.append(device.id)

    return JsonResponse(
        {
            "status": "success",
            "active_usernames": list(active_usernames),
            "offline_routers": offline_routers,
        }
    )


@login_required
def api_downdetector_data(request):
    """
    Returns the JSON data of monitored services status.
    """
    from billing.models import MonitoredService

    services = MonitoredService.objects.all().order_by("name")
    data = []
    for s in services:
        data.append(
            {
                "id": s.id,
                "name": s.name,
                "type": s.service_type,
                "status": s.status,
                "latency_ms": s.latency_ms,
                "last_checked": (
                    s.last_checked.strftime("%Y-%m-%d %H:%M:%S")
                    if s.last_checked
                    else None
                ),
            }
        )
    return JsonResponse({"services": data})
