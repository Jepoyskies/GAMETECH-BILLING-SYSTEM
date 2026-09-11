from collections import defaultdict
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from billing.models import (
    AccountType,
    AddOnRequest,
    Agent,
    Barangay,
    Customer,
    Payment,
    SubscriptionPlan,
    SystemAdmin,
    SystemLog,
)
from network_manager.models import MikrotikDevice, NapBox


@login_required
def system_logs_view(request):
    logs = SystemLog.objects.all()

    # Search filter
    search_query = request.GET.get("search", "").strip()
    if search_query:
        logs = logs.filter(
            Q(table_name__icontains=search_query)
            | Q(changed_by__icontains=search_query)
            | Q(action__icontains=search_query)
            | Q(old_data__icontains=search_query)
            | Q(new_data__icontains=search_query)
            | Q(target_name__icontains=search_query)
        )

    # Action filter
    action_filter = request.GET.get("action_filter", "").strip().upper()
    if action_filter == "ADD":
        logs = logs.filter(action__iexact="ADD")
    elif action_filter == "UPDATE":
        logs = logs.filter(action__iexact="UPDATE")
    elif action_filter == "DELETE":
        logs = logs.filter(action__iexact="DELETE")

    # Date filter
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if date_from:
        logs = logs.filter(changed_at__gte=f"{date_from} 00:00:00")
    if date_to:
        logs = logs.filter(changed_at__lte=f"{date_to} 23:59:59")

    # Sorting
    sort_column = request.GET.get("sort", "changed_at")
    sort_dir = request.GET.get("dir", "desc").lower()

    allowed_sort_columns = [
        "changed_at",
        "table_name",
        "record_id",
        "action",
        "changed_by",
    ]
    if sort_column not in allowed_sort_columns:
        sort_column = "changed_at"

    order_prefix = "-" if sort_dir == "desc" else ""
    logs = logs.order_by(f"{order_prefix}{sort_column}")

    # Scope / Limit filter: Default to latest 500 records unless a date/search filter is explicitly set
    total_db_records = SystemLog.objects.count()
    today_records_count = SystemLog.objects.filter(changed_at__date=timezone.now().date()).count()

    scope = request.GET.get("scope", "500" if not (date_from or date_to or search_query) else "all")
    is_capped = False

    if scope == "today":
        logs = logs.filter(changed_at__date=timezone.now().date())
    elif scope == "7d":
        logs = logs.filter(changed_at__gte=timezone.now() - timedelta(days=7))
    elif scope == "30d":
        logs = logs.filter(changed_at__gte=timezone.now() - timedelta(days=30))
    elif scope == "500" and not (date_from or date_to):
        latest_ids = list(logs.values_list("id", flat=True)[:500])
        logs = SystemLog.objects.filter(id__in=latest_ids).order_by(f"{order_prefix}{sort_column}")
        if total_db_records > 500:
            is_capped = True

    # Pagination
    paginator = Paginator(logs, 10)  # 10 logs per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Initialize all targets to None
    for log in page_obj:
        log.target_customer = None
        log.target_icon = "fas fa-cube"

    # Group record IDs by table
    table_ids = defaultdict(list)
    for log in page_obj:
        if str(log.record_id).isdigit():
            table_ids[log.table_name].append(log.record_id)

    # Bulk fetch names
    resolved_names = defaultdict(dict)

    if "Customer" in table_ids:
        qs = Customer.objects.filter(id__in=table_ids["Customer"]).values(
            "id", "full_name"
        )
        resolved_names["Customer"] = {
            str(c["id"]): (c["full_name"], "fas fa-user") for c in qs
        }

    if "Payment" in table_ids:
        qs = (
            Payment.objects.filter(id__in=table_ids["Payment"])
            .select_related("customer")
            .values("id", "customer__full_name")
        )
        resolved_names["Payment"] = {
            str(p["id"]): (p["customer__full_name"] or "Unknown", "fas fa-user-circle")
            for p in qs
        }

    if "AddOnRequest" in table_ids:
        qs = (
            AddOnRequest.objects.filter(id__in=table_ids["AddOnRequest"])
            .select_related("customer")
            .values("id", "customer__full_name")
        )
        resolved_names["AddOnRequest"] = {
            str(a["id"]): (a["customer__full_name"] or "Unknown", "fas fa-plus-circle")
            for a in qs
        }

    if "MikrotikDevice" in table_ids:
        qs = MikrotikDevice.objects.filter(id__in=table_ids["MikrotikDevice"]).values(
            "id", "device_name"
        )
        resolved_names["MikrotikDevice"] = {
            str(m["id"]): (m["device_name"], "fas fa-server") for m in qs
        }

    if "NapBox" in table_ids:
        qs = NapBox.objects.filter(id__in=table_ids["NapBox"]).values("id", "napbox_no")
        resolved_names["NapBox"] = {
            str(n["id"]): (n["napbox_no"], "fas fa-box") for n in qs
        }

    if "SubscriptionPlan" in table_ids:
        qs = SubscriptionPlan.objects.filter(
            id__in=table_ids["SubscriptionPlan"]
        ).values("id", "name")
        resolved_names["SubscriptionPlan"] = {
            str(s["id"]): (s["name"], "fas fa-wifi") for s in qs
        }

    if "Agent" in table_ids:
        qs = Agent.objects.filter(id__in=table_ids["Agent"]).values("id", "name")
        resolved_names["Agent"] = {
            str(a["id"]): (a["name"], "fas fa-user-tie") for a in qs
        }

    if "SystemAdmin" in table_ids:
        qs = SystemAdmin.objects.filter(id__in=table_ids["SystemAdmin"]).values(
            "id", "username"
        )
        resolved_names["SystemAdmin"] = {
            str(s["id"]): (s["username"], "fas fa-user-shield") for s in qs
        }

    if "Barangay" in table_ids:
        qs = Barangay.objects.filter(id__in=table_ids["Barangay"]).values("id", "name")
        resolved_names["Barangay"] = {
            str(b["id"]): (b["name"], "fas fa-map-marker-alt") for b in qs
        }

    if "AccountType" in table_ids:
        qs = AccountType.objects.filter(id__in=table_ids["AccountType"]).values(
            "id", "type_name"
        )
        resolved_names["AccountType"] = {
            str(a["id"]): (a["type_name"], "fas fa-tags") for a in qs
        }

    # Attach to logs
    for log in page_obj:
        name = None
        icon = None

        if hasattr(log, "target_name") and log.target_name:
            name = log.target_name
            if log.table_name == "Customer":
                icon = "fas fa-user"
            elif log.table_name == "Payment":
                icon = "fas fa-user-circle"
            elif log.table_name == "AddOnRequest":
                icon = "fas fa-plus-circle"
            elif log.table_name == "MikrotikDevice":
                icon = "fas fa-server"
            elif log.table_name == "NapBox":
                icon = "fas fa-box"
            elif log.table_name == "SubscriptionPlan":
                icon = "fas fa-wifi"
            elif log.table_name == "Agent":
                icon = "fas fa-user-tie"
            elif log.table_name == "SystemAdmin":
                icon = "fas fa-user-shield"
            elif log.table_name == "Barangay":
                icon = "fas fa-map-marker-alt"
            elif log.table_name == "AccountType":
                icon = "fas fa-tags"
        elif log.table_name in resolved_names:
            name, icon = resolved_names[log.table_name].get(
                str(log.record_id), (None, None)
            )

        if name:
            log.target_customer = name
            log.target_icon = icon or "fas fa-cube"

    # Attach actor roles for the USER column
    admin_roles = dict(SystemAdmin.objects.values_list("username", "role"))
    agent_names = set(Agent.objects.values_list("user__username", flat=True))

    for log in page_obj:
        user_str = log.changed_by or "Unknown"
        if user_str.startswith("System/"):
            log.actor_role = "System"
        elif user_str in admin_roles:
            log.actor_role = admin_roles[user_str]
        elif user_str in agent_names:
            log.actor_role = "Agent"
        else:
            log.actor_role = "User"

    # Reconstruct query string for pagination links
    query_params = request.GET.copy()
    if "page" in query_params:
        del query_params["page"]

    context = {
        "logs": page_obj,
        "search": search_query,
        "action_filter": action_filter,
        "date_from": date_from,
        "date_to": date_to,
        "sort": sort_column,
        "dir": sort_dir,
        "scope": scope,
        "is_capped": is_capped,
        "total_db_records": total_db_records,
        "today_records_count": today_records_count,
        "query_params": query_params.urlencode(),
        "page_range": page_obj.paginator.get_elided_page_range(
            page_obj.number, on_each_side=2, on_ends=1
        ),
    }
    return render(request, "billing/logs.html", context)
