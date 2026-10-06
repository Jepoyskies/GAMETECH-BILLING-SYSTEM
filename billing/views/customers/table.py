"""
Helpers behind the customer table on /customers/.

Split out of list.py so the view itself stays readable. These are all pure
read paths: nothing here writes to a router or mutates the database.

  * _bulk_dispatch_labels  - resolves dispatch status for many customers with
                             two queries instead of one per row (N+1 killer).
  * _search_customers      - the in-memory search staff type into the table.
  * _datatables_json       - server-side payload for DataTables.
  * mac_history_view       - unrelated to the table, it just lived here.
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render


def _bulk_dispatch_labels(customer_ids):
    """Return {customer_id: "Installation" | "Repair" | ...} for open work.

    `Customer.dispatch_status` falls through to
    `self.dispatches.filter(done_at__isnull=True).first()`, and the status cell
    calls it for every row -- 2,038 separate queries on every page load, which
    was the single biggest cost on this page. Two bulk queries pin the answer
    onto each row instead, so the template never touches the database.

    New-style JobTicket statuses are UPPERCASE and must mirror
    `Customer.active_dispatch_ticket` exactly, or the badge disappears.
    """
    labels = {}
    if not customer_ids:
        return labels

    try:
        from dispatch.models import JobTicket

        type_map = {
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
                customer_id__in=customer_ids,
                status__in=[
                    "PENDING", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "QA_PASSED",
                ],
            )
            .values("customer_id", "ticket_type")
            .order_by("customer_id", "-created_at")
        )
        for r in rows:
            cid = r["customer_id"]
            if cid in labels:
                continue
            t = r["ticket_type"]
            labels[cid] = type_map.get(t, (t or "").replace("_", " ").title())
    except Exception:
        pass

    # Legacy DispatchRecord, only for customers the tickets did not cover.
    try:
        from dispatch.models import DispatchRecord

        legacy = (
            DispatchRecord.objects.filter(
                customer_id__in=customer_ids, done_at__isnull=True
            )
            .values("customer_id", "source_tab")
            .order_by("customer_id", "-created_at")
        )
        for r in legacy:
            cid = r["customer_id"]
            if cid in labels:
                continue
            labels[cid] = (
                "Repair" if r.get("source_tab") == "CLIENT_CONCERNS" else "Installation"
            )
    except Exception:
        pass

    return labels


def _search_customers(rows, term):
    """Case-insensitive search across the fields staff actually search by.

    Runs over the already-fetched rows rather than issuing a second query, so
    the lifecycle resolution stays consistent with what is displayed.
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
    """Server-side payload so DataTables never needs the whole table at once."""
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