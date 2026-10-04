"""
Customer CSV export.

There was no way to export the subscriber list, which is exactly what you need
after importing 2,041 rows: export, diff against the old system, and prove the
import landed. The dispatch and Cignal exports already existed; this closes the
gap for customers.

Respects the active filters on /customers/ so staff can export "just the problem
rows" (e.g. status=expired) rather than always dumping everything.
"""
import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

from billing.decorators import billing_required, role_required
from billing.models import Customer

# Never export secrets. PPPoE passwords and portal password hashes stay in the DB.
COLUMNS = [
    ("pppoe_username", "PPPoE Username"),
    ("full_name", "Full Name"),
    ("phone", "Phone"),
    ("email", "Email"),
    ("address", "Address"),
    ("barangay", "Barangay"),
    ("plan", "Plan"),
    ("plan_price", "Monthly Price"),
    ("status", "Status"),
    ("installation_status", "Installation"),
    ("expires_at", "Expires At"),
    ("outstanding_balance", "Outstanding Balance"),
    ("mikrotik_device", "Router"),
    ("sync_status", "Sync Status"),
    ("agent", "Agent"),
    ("is_connected", "Connected"),
    ("installed_at", "Installed At"),
    ("created_at", "Created At"),
]


@login_required
@billing_required
def export_customers_csv(request):
    """Export the subscriber list as CSV, honouring the list page filters."""
    qs = Customer.objects.select_related("plan", "mikrotik_device", "barangay", "agent")

    q = (request.GET.get("q") or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(pppoe_username__icontains=q)
            | Q(full_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(address__icontains=q)
        )

    status = (request.GET.get("status") or "").strip()
    if status and status.lower() != "all":
        qs = qs.filter(status=status)

    inst = (request.GET.get("installation_status") or "").strip()
    if inst and inst.lower() != "all":
        qs = qs.filter(installation_status=inst)

    sync = (request.GET.get("sync_status") or "").strip()
    if sync and sync.lower() != "all":
        qs = qs.filter(sync_status=sync)

    # "problem rows" preset used during a cutover review
    if request.GET.get("issues") == "1":
        from django.db.models import Q
        qs = qs.filter(
            Q(expires_at__isnull=True)
            | Q(sync_status__in=["Unverified", "Pending", "Blocked", "Failed"])
            | Q(outstanding_balance__gt=0)
        )

    qs = qs.order_by("pppoe_username")

    resp = HttpResponse(content_type="text/csv")
    stamp = timezone.now().strftime("%Y%m%d_%H%M")
    resp["Content-Disposition"] = f'attachment; filename="customers_{stamp}.csv"'

    writer = csv.writer(resp)
    writer.writerow([label for _, label in COLUMNS])

    for c in qs.iterator(chunk_size=500):
        row = []
        for attr, _label in COLUMNS:
            if attr == "barangay":
                row.append(c.barangay.name if c.barangay else "")
            elif attr == "plan":
                row.append(c.plan.name if c.plan else "")
            elif attr == "plan_price":
                row.append(str(c.plan.price) if c.plan else "")
            elif attr == "mikrotik_device":
                row.append(c.mikrotik_device.device_name if c.mikrotik_device else "")
            elif attr == "agent":
                row.append((c.agent.name if c.agent else "")
                           or (c.original_agent.name if c.original_agent else ""))
            elif attr == "is_connected":
                row.append("Yes" if getattr(c, "is_connected", False) else "No")
            elif attr in ("expires_at", "installed_at", "created_at"):
                v = getattr(c, attr, None)
                row.append(v.strftime("%Y-%m-%d %H:%M") if v else "")
            else:
                row.append("" if getattr(c, attr, None) is None else str(getattr(c, attr)))
        writer.writerow(row)

    return resp