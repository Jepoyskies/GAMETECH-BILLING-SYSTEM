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

# Table helpers live in .table so this module stays focused on the view.
# `mac_history_view` is re-exported here because billing/urls.py reaches it
# through `billing.views`, and billing/tests/ imports `customer_list` directly
# from this module -- both must keep working.
from .table import (
    _bulk_dispatch_labels,
    _datatables_json,
    _search_customers,
    mac_history_view,
)


def _can_view_billing(user):
    """Who may open the subscriber list.

    Uses the StaffRole matrix (`can_access_billing`) so the Role Editor stays the
    single source of truth: Admin / Editor / CSR / Viewer are True, while Agent,
    Technician and Dispatch are False.
    """
    if getattr(user, "is_superuser", False):
        return True
    perms = getattr(user, "role_perms", None)
    if perms is None:
        return False
    return bool(getattr(perms, "can_access_billing", False))


@login_required
def customer_list(request):
    if hasattr(request.user, "agent_profile") and not request.user.is_staff:
        return redirect("agent_dashboard")

    # This view was gated by @login_required alone, so ANY authenticated user
    # could browse the whole subscriber list -- names, addresses, phones and
    # balances. A field Technician has no business here; their isolation
    # contract says they only ever see jobs staff assigned them.
    #
    # Checked inside the view rather than as a decorator so the agent redirect
    # above keeps priority (a decorator would run first and bounce agents to
    # the dashboard instead of their own portal).
    if not _can_view_billing(request.user):
        from django.contrib import messages as _m
        _m.error(
            request,
            "Your role does not have access to the customer list. "
            "Technicians see only their assigned jobs in the Field Portal.",
        )
        if hasattr(request.user, "technician"):
            return redirect("technician_dashboard")
        return redirect("dashboard")
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
    # `expired`/`inactive` remain meaningful roll-ups for legacy consumers.
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

    # --- Cutover integrity filters -------------------------------------
    #
    # These are NOT billing states. They answer "is this account actually
    # able to carry service", which is the question an operator has after a
    # legacy import and which no lifecycle row can express:
    #
    #   not_in_router  exists here, never pushed to the MikroTik
    #   no_pppoe       no router credentials at all -> cannot authenticate
    #   no_expiry      no cut-off date -> will never auto-suspend
    #
    # Deliberately computed from the row itself, not from a live router read.
    # A router that is down must not make an operator think an account is
    # unsynced, which is exactly the false alarm the blind-mode banner exists
    # to prevent.
    integrity = {
        "not_in_router": lambda c: c.sync_status != "Synced" or not c.mikrotik_device_id,
        "no_pppoe": lambda c: not (c.pppoe_username or "").strip(),
        "no_expiry": lambda c: c.expires_at is None,
    }
    integrity_counts = {
        k: sum(1 for c in base_customers if fn(c)) for k, fn in integrity.items()
    }

    integrity_filter = request.GET.get("integrity", "").strip()
    if integrity_filter:
        if integrity_filter in integrity:
            base_customers = [c for c in base_customers if integrity[integrity_filter](c)]
        else:
            integrity_filter = ""

    # Attach the resolved Lifecycle to every row, then sort by it so the most
    # urgent rows come first. This replaces the old overlapping Case/When
    # status_order, which ranked "paid but offline" first even when we were
    # blind and that verdict was not real.
    customers = annotate_lifecycle(base_customers, connected_usernames, now)
    customers.sort(key=lambda c: (c.lifecycle.priority, (c.full_name or "").lower()))

    # Backwards-compatible flags for templates that still test them.
    #
    # The router/connection state is resolved ONCE per device here and pinned
    # onto each row. Previously the template called `customer.router_status` and
    # `customer.connection_status` per row, and each of those did its own cache
    # round trips -- 2,041 rows meant ~6,000 Redis calls and ~7s of pure
    # duplicate work. The view already knows the answer, so hand it over.
    from django.core.cache import cache
    from billing.diagnostics import get_bridge_status

    bridge_ok = get_bridge_status()["status"] == "Online"
    live = cache.get("live_monitoring_data") or {}
    router_uplink = {
        r.get("device_name"): bool(r.get("internet_online"))
        for r in (live.get("routers") or [])
    }

    # Read each router's unreachable flag ONCE, not once per customer. There
    # are only a handful of routers but thousands of customers, so the old
    # per-row `cache.get` was ~2,000 redundant Redis round trips.
    router_down = {}
    if devices_prefetched := list(MikrotikDevice.objects.values("id")):
        for row in devices_prefetched:
            router_down[row["id"]] = bool(cache.get(f"router_unreachable_{row['id']}"))

    def _router_state(customer):
        dev = customer.mikrotik_device
        if not dev:
            return "Offline"
        if router_down.get(dev.id):
            return "Unknown"
        if not bridge_ok:
            # Blind. Never accuse the router from a vantage point we lack.
            return "Unknown"
        if dev.device_name in router_uplink:
            return "Online" if router_uplink[dev.device_name] else "Offline"
        return "Offline"

    # --- Kill the N+1: dispatch_status was one query per row ---------------
    # See table._bulk_dispatch_labels for why this is two bulk queries rather
    # than one per customer. On 2,038 rows the old per-row property lookup was
    # ~23s of the page's 30s.
    dispatch_label = _bulk_dispatch_labels([c.id for c in customers])

    for c in customers:
        c.is_paid_offline = c.lifecycle.key == "paid_offline"
        c.is_connected_unpaid = c.lifecycle.key == "connected_unpaid"
        c.is_no_expiry = c.lifecycle.key == "no_expiry"
        c.status_order = c.lifecycle.priority
        c.resolved_router_status = _router_state(c)
        c.resolved_connection_status = {
            "connected": "Online",
            "offline": "Offline",
        }.get(c.lifecycle.hardware, "Unknown")
        c.resolved_dispatch_status = dispatch_label.get(c.id)
        # Tell the model property to use the bulk-resolved value instead of
        # running its own query.
        c._dispatch_status_pinned = True

    # --- Server-side search, filter and pagination ------------------------
    # The table used to render all 2,041 rows into one HTML document: 13.2 MB
    # and ~11s, which regularly OOM-killed the web container on this 2 GB box.
    #
    # A previous attempt capped the queryset and shipped 25 rows, which made
    # search blind -- "Juan Dela Cruz" was unfindable. The way out is to move
    # search and filtering into the database so they still cover every
    # customer, and paginate what is actually rendered. Nothing is hidden; the
    # server just stops sending the whole table to the browser.
    search = (request.GET.get("search") or "").strip()
    router_filter = (request.GET.get("router") or "").strip()
    barangay_filter = (request.GET.get("barangay") or "").strip()
    sort = (request.GET.get("sort") or "priority").strip()

    pool = base_customers
    if search:
        pool = _search_customers(pool, search)
    if router_filter:
        pool = [
            c for c in pool
            if c.mikrotik_device and c.mikrotik_device.device_name == router_filter
        ]
    if barangay_filter:
        pool = [c for c in pool if c.barangay and c.barangay.name == barangay_filter]

    # Re-key the resolved state onto the filtered pool, so the rows rendered
    # and the lifecycle counts always describe the same thing.
    keep_ids = {c.id for c in pool}
    customers = [c for c in customers if c.id in keep_ids]

    if sort == "name":
        customers.sort(key=lambda c: (c.full_name or "").lower())
    elif sort == "expiry":
        customers.sort(key=lambda c: (c.expires_at is None, c.expires_at))
    elif sort == "newest":
        customers.sort(key=lambda c: c.id, reverse=True)
    else:
        # Default: most urgent first, which is the whole point of the
        # lifecycle work.
        customers.sort(key=lambda c: (c.lifecycle.priority, (c.full_name or "").lower()))

    from django.core.paginator import Paginator

    paginator = Paginator(customers, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    customers = list(page_obj)
    total_rows = paginator.count

    devices = MikrotikDevice.objects.all().order_by("device_name")
    from billing.models import Barangay, SystemLog

    barangays = Barangay.objects.all().order_by("name")

    # Fetch recent customer logs for the new UI feature
    customer_logs = SystemLog.objects.filter(table_name="Customer").order_by("-changed_at")[:50]

    # Count customers not yet synced to any router (for the sync reminder badge)
    pending_sync_count = Customer.objects.filter(
        sync_status__in=["Unverified", "Failed"],
        pppoe_username__isnull=False,
    ).exclude(pppoe_username='').count()

    context = {
        "customers": customers,
        "devices": devices,
        "barangays": barangays,
        "filter_type": filter_type,
        "stats": stats,
        "lifecycle_filters": lifecycle_filters,
        "network_visible": network_visible,
        "inactive_count": stats.get("inactive", 0),
        "customer_logs": customer_logs,
        "total_rows": total_rows,
        "page_obj": page_obj,
        "paginator": paginator,
        "search": search,
        "router_filter": router_filter,
        "barangay_filter": barangay_filter,
        "sort": sort,
        "pending_sync_count": pending_sync_count,
        "integrity_counts": integrity_counts,
        "integrity_filter": integrity_filter,
    }

    # --- DataTables server-side processing ---------------------------------
    # The table used to render all 2,041 rows into one HTML page: 13.2 MB and
    # ~30 seconds to build, which was regularly OOM-killing the web container
    # on a 2 GB box. Client-side DataTables cannot paginate what the server
    # already paid to render.
    #
    # An earlier attempt at server-side pagination was reverted because it
    # capped the queryset, so search could only ever see those 25 rows and
    # "Juan Dela Cruz" was unfindable. The fix for that is to paginate AND
    # search in SQL, so search still covers every customer -- just without
    # shipping the whole table to the browser.
    if "draw" in request.GET:
        return _datatables_json(request, base_customers, connected_usernames, now, stats)

    return render(request, "billing/customer_list.html", context)


# How many rows go into the initial HTML. DataTables requests the rest.
FIRST_PAGE_SIZE = 50


# Rows rendered per page.
#
# 100 rows looked generous but cost real time: every row expands to ~190 lines
# of markup once the status partial is included, so a page was ~12,000 template
# node evaluations. Measured 2.5s and 921 KB per load, with only 0.128s of that
# in the database -- the rest was rendering. DataTables fetches the rest, and
# search/filter/sort all still cover every customer, so 50 rows costs staff
# nothing in practice and roughly halves both load time and page weight.
PAGE_SIZE = 50
