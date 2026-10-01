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
    if hasattr(request.user, "agent_profile") and not request.user.is_staff:
        return redirect("agent_dashboard")
    from network_manager.models import MikrotikDevice
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Case, When, Value, IntegerField, BooleanField, Count, Q

    now = timezone.now()
    seven_days_from_now = now + timedelta(days=7)
    seven_days_ago = now - timedelta(days=7)

    # Total is the only count computed in SQL. Every other KPI is derived from
    # the single resolve() pass below, so the pills are mutually exclusive and
    # always sum to the total. The old overlapping Q() filters double-counted
    # and did not reconcile (852+388+1240+402+389+16 = 2,047 vs 2,041 total).
    stats = {
        "total": Customer.objects.exclude(status="closed_not_installed").count(),
        # Placeholders overwritten by the resolve() pass.
        "active": 0, "expiring": 0, "expired": 0, "inactive": 0,
        "no_expiry": 0, "paid_offline": 0, "paid_but_offline": 0,
    }

    # --- Connectivity, honestly measured ---------------------------------
    # `network_visibility()` returns connected_usernames=None when we cannot
    # see the routers. That None is what stops a router outage from being
    # reported as "every paid customer is offline" (it once showed 1,240).
    from billing.customer_state import (
        FILTERS,
        LIFECYCLES,
        annotate as annotate_lifecycle,
        network_visibility,
        resolve,
    )

    network_visible, connected_usernames = network_visibility()

    base_customers = list(
        Customer.objects.select_related(
            "plan", "agent", "barangay", "mikrotik_device"
        )
        .exclude(status="closed_not_installed")
    )

    # Resolve every customer's state once, then derive both the KPI counts
    # and the filter from that same pass. Counts and rows can never disagree.
    resolved = [resolve(c, connected_usernames, now) for c in base_customers]
    by_key = {c.id: lc for c, lc in zip(base_customers, resolved)}

    # One pass, one truth. Counts come from the same Lifecycle objects the
    # table rows render, so a KPI can never disagree with its own list.
    for key in LIFECYCLES:
        stats[key] = 0
    for lc in by_key.values():
        stats[lc.key] += 1

    # (key, label, icon, tone, count) -- the template renders counts directly
    # rather than doing a dict lookup, which needs a custom filter.
    lifecycle_filters = [
        (key, label, icon, tone, stats.get(key, 0))
        for key, label, icon, tone in FILTERS
    ]

    # Legacy aliases so existing templates/JS do not break.
    stats["paid_but_offline"] = stats["paid_offline"]
    stats["active"] = stats["connected_paid"]
    stats["expiring"] = stats["expiring"]
    stats["no_expiry"] = stats["no_expiry"]
    # `expired`/`inactive` remain meaningful totals for legacy consumers.
    stats["expired"] = stats["connected_unpaid"] + stats["lapsed_offline"]
    stats["inactive"] = stats["suspended"] + stats["inactive"] + stats["pulled_out"]
    stats["network_visible"] = network_visible

    filter_type = request.GET.get("filter", "all")

    valid_filter_keys = {k for k, _, _, _ in FILTERS}
    if filter_type not in valid_filter_keys and filter_type not in ("all",):
        filter_type = "all"

    if filter_type != "all":
        keep = {cid for cid, lc in by_key.items() if lc.key == filter_type}
        base_customers = [c for c in base_customers if c.id in keep]

    # Lifecycle was already resolved onto each row. Sort by that same
    # resolution so the most urgent rows are physically first, then by name.
    # This replaces the old overlapping Case/When status_order, which ranked
    # "paid but offline" first even when we were blind and that verdict was
    # not real.
    customers.sort(key=lambda c: (c.lifecycle.priority, (c.full_name or "").lower()))

    # Backwards-compatible flags for templates that still test them.
    for c in customers:
        c.is_paid_offline = c.lifecycle.key == "paid_offline"
        c.is_connected_unpaid = c.lifecycle.key == "connected_unpaid"
        c.is_no_expiry = c.lifecycle.key == "no_expiry"
        c.status_order = c.lifecycle.priority

    # NOTE: do NOT reintroduce server-side pagination here.
    # The table is a client-side DataTable, so capping the queryset server-side
    # silently limited search (and the router/barangay column filters) to those
    # 25 rows -- "Juan Dela Cruz" could not be found among 2,041 customers.
    # DataTables already pages client-side; feed it every row.

    devices = MikrotikDevice.objects.all().order_by("device_name")
    from billing.models import Barangay, SystemLog

    barangays = Barangay.objects.all().order_by("name")
    
    # Fetch recent customer logs for the new UI feature
    customer_logs = SystemLog.objects.filter(table_name="Customer").order_by("-changed_at")[:50]
    
    return render(
        request,
        "billing/customer_list.html",
        {
            "customers": customers,
            "devices": devices,
            "barangays": barangays,
            "filter_type": filter_type,
            "stats": stats,
            "lifecycle_filters": lifecycle_filters,
            "network_visible": network_visible,
            "inactive_count": stats.get("inactive", 0),
            "customer_logs": customer_logs,
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
