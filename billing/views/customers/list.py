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
from billing.views.services import get_categorized_plans


@login_required
def customer_list(request):
    from network_manager.models import MikrotikDevice
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Case, When, Value, IntegerField, BooleanField, Count, Q

    now = timezone.now()
    seven_days_from_now = now + timedelta(days=7)
    seven_days_ago = now - timedelta(days=7)

    # Dynamic counts for Top Stat Pills
    stats = Customer.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(expires_at__gt=seven_days_from_now, status="active")),
        expiring=Count("id", filter=Q(expires_at__gt=now, expires_at__lte=seven_days_from_now, status="active")),
        inactive=Count("id", filter=Q(status__in=["suspended", "inactive", "pull out"]) | Q(expires_at__lte=seven_days_ago)),
        offline=Count("id", filter=Q(status__in=["suspended", "inactive", "pull out"]) | Q(expires_at__lte=now)),
    )

    # MikroTik Live Connectivity for Paid but Offline metric
    from django.core.cache import cache
    from network_manager.services import MikrotikAPI

    connected_usernames = cache.get("active_pppoe_usernames_set")
    if connected_usernames is None:
        connected_usernames = set()
        for device in MikrotikDevice.objects.all():
            try:
                api = MikrotikAPI(device)
                for au in api.get_active_pppoe_users():
                    name = au.get("name")
                    if name:
                        connected_usernames.add(name)
            except Exception:
                pass
        cache.set("active_pppoe_usernames_set", connected_usernames, 30)

    # Calculate Paid but Offline subscribers (active billing status but disconnected from router)
    active_paid_customers = Customer.objects.filter(
        expires_at__gt=now,
        status="active"
    ).values("id", "pppoe_username")

    paid_but_offline_ids = [
        c["id"] for c in active_paid_customers
        if not c["pppoe_username"] or c["pppoe_username"] not in connected_usernames
    ]
    stats["paid_but_offline"] = len(paid_but_offline_ids)

    customers = Customer.objects.select_related(
        "plan", "agent", "barangay", "mikrotik_device"
    ).all()

    filter_type = request.GET.get("filter", "all")

    if filter_type == "active":
        customers = customers.filter(
            expires_at__gt=seven_days_from_now, status="active"
        )
    elif filter_type == "expiring":
        customers = customers.filter(
            expires_at__gt=now, expires_at__lte=seven_days_from_now, status="active"
        )
    elif filter_type in ["paid_offline", "paid_but_offline"]:
        customers = customers.filter(id__in=paid_but_offline_ids)
    elif filter_type == "expired":
        customers = customers.filter(expires_at__lte=now, expires_at__gt=seven_days_ago)
    elif filter_type == "inactive":
        customers = customers.filter(expires_at__lte=seven_days_ago)

    customers = customers.annotate(
        is_paid_offline=Case(
            When(id__in=paid_but_offline_ids, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        status_order=Case(
            When(id__in=paid_but_offline_ids, then=Value(0)),  # Top Priority: Active accounts offline
            When(status="active", then=Value(1)),
            When(status="pending", then=Value(2)),
            When(status="suspended", then=Value(3)),
            When(status="expired", then=Value(4)),
            When(status="inactive", then=Value(5)),
            When(status="pull out", then=Value(6)),
            default=Value(7),
            output_field=IntegerField(),
        ),
    ).order_by("status_order", "full_name")

    devices = MikrotikDevice.objects.all().order_by("device_name")
    from billing.models import Barangay

    barangays = Barangay.objects.all().order_by("name")
    return render(
        request,
        "billing/customer_list.html",
        {
            "customers": customers,
            "devices": devices,
            "barangays": barangays,
            "filter_type": filter_type,
            "stats": stats,
            "inactive_count": stats.get("inactive", 0),
        },
    )


@login_required
def mac_history_view(request):
    from billing.models import CustomerMacHistory

    history = CustomerMacHistory.objects.select_related("customer").all()
    search = request.GET.get("search", "").strip()
    if search:
        history = history.filter(
            Q(customer__full_name__icontains=search)
            | Q(mac_address__icontains=search)
            | Q(customer__id__icontains=search)
        )
    return render(request, "billing/mac_history.html", {"history": history})
