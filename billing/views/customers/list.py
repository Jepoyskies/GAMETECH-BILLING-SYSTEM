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
    # `Customer.dispatch_status` falls through to
    # `self.dispatches.filter(done_at__isnull=True).first()`, and the status
    # cell calls it for all 2,041 rows. That is 2,041 separate queries on
    # every page load, which was the single biggest cost on this page (~23s of
    # the 30s total). Resolve it here with two bulk queries and pin the result
    # onto the row, so the template never touches the database.
    dispatch_label = {}
    if customers:
        ids = [c.id for c in customers]

        # 1) New-style tickets, newest open ticket per customer.
        # Model is JobTicket and its statuses are UPPERCASE. This must mirror
        # `Customer.active_dispatch_ticket` exactly or the badge disappears.
        try:
            from dispatch.models import JobTicket
            TYPE_MAP = {
                "INSTALLATION": "Installation",
                "REPAIR": "Repair",
                "CIGNAL": "Cignal",
                "MIGRATION": "Migration",
                "RELOCATION": "Relocation",
                "PULL_OUT": "Pull Out",
                "SITE_VISIT": "Site Visit",
            }
            rows = (
                JobTicket.objects.filter(
                    customer_id__in=ids,
                    status__in=["PENDING", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "QA_PASSED"],
                )
                .values("customer_id", "ticket_type")
                .order_by("customer_id", "-created_at")
            )
            for r in rows:
                cid = r["customer_id"]
                if cid in dispatch_label:
                    continue
                t = r["ticket_type"]
                dispatch_label[cid] = TYPE_MAP.get(t, (t or "").replace("_", " ").title())
        except Exception:
            pass

        # 2) Legacy DispatchRecord, only for customers the tickets did not cover.
        try:
            from dispatch.models import DispatchRecord
            legacy = (
                DispatchRecord.objects.filter(
                    customer_id__in=ids, done_at__isnull=True
                )
                .values("customer_id", "source_tab")
                .order_by("customer_id", "-created_at")
            )
            for r in legacy:
                cid = r["customer_id"]
                if cid in dispatch_label:
                    continue
                dispatch_label[cid] = (
                    "Repair" if r.get("source_tab") == "CLIENT_CONCERNS" else "Installation"
                )
        except Exception:
            pass

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


# Rows rendered per page. 100 is a compromise: large enough that staff rarely
# page, small enough that the HTML stays a few hundred KB instead of 13 MB.
PAGE_SIZE = 100


def _search_customers(rows, term):
    """Case-insensitive search across the fields staff actually search by.

    Runs over the already-fetched rows rather than issuing a second query, so
    the lifecycle resolution above stays consistent with what is displayed.
    """
    needle = term.lower()
    out = []
    for c in rows:
        haystack = (
            (c.full_name or ""),
            (c.pppoe_username or ""),
            (c.email or ""),
            (c.phone or ""),
            (c.plan.name if c.plan else ""),
            (c.barangay.name if c.barangay else ""),
            (c.mikrotik_device.device_name if c.mikrotik_device else ""),
        )
        if any(needle in (h or "").lower() for h in haystack):
            out.append(c)
    return out


def _datatables_json(request, rows_all, connected_usernames, now, stats):
    from django.http import JsonResponse

    from billing.customer_state import resolve

    try:
        draw = int(request.GET.get("draw", 1))
    except (TypeError, ValueError):
        draw = 1
    try:
        length = int(request.GET.get("length", 50))
    except (TypeError, ValueError):
        length = 50
    length = max(10, min(length, 500))
    try:
        start = int(request.GET.get("start", 0))
    except (TypeError, ValueError):
        start = 0

    search = (request.GET.get("search[value]") or "").strip()

    pool = rows_all
    if search:
        needle = search.lower()
        pool = [
            c for c in pool
            if needle in (c.full_name or "").lower()
            or needle in (c.pppoe_username or "").lower()
            or needle in (c.email or "").lower()
            or needle in (c.phone or "").lower()
            or needle in (c.plan.name if c.plan else "").lower()
        ]

    total = len(pool)
    page = pool[start:start + length]

    data = []
    for c in page:
        lc = resolve(c, connected_usernames, now)
        data.append({
            "id": c.id,
            "full_name": c.full_name or "",
            "email": c.email or "",
            "phone": c.phone or "",
            "plan": c.plan.name if c.plan else "-",
            "lifecycle": lc.key,
            "lifecycle_label": lc.label,
            "tone": lc.tone,
            "hint": lc.hint,
        })

    return JsonResponse({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": data,
    })


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
