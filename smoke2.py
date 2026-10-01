"""Curated smoke test of the pages staff actually use.

The generic URL walker hung because many views legitimately open a router
connection, and three of four routers are currently down. This hits the real
business pages with a hard per-page view of what failed.
"""
import time
import traceback

from django.contrib.auth import get_user_model
from django.test import RequestFactory

User = get_user_model()
rf = RequestFactory()
su = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()

from billing.models import Customer, SubscriptionPlan, Payment
from network_manager.models import MikrotikDevice

cid = Customer.objects.order_by("id").values_list("id", flat=True).first() or 1
pid = SubscriptionPlan.objects.order_by("id").values_list("id", flat=True).first() or 1
did = MikrotikDevice.objects.order_by("id").values_list("id", flat=True).first() or 1
payid = Payment.objects.order_by("id").values_list("id", flat=True).first() or 0

PAGES = [
    "/", "/login/", "/logout/", "/dashboard/", "/dashboard/analytics/",
    "/customers/", "/customers/?filter=all",
    "/customers/?filter=connected_unpaid", "/customers/?filter=paid_offline",
    "/customers/?filter=expiring", "/customers/?filter=connected_paid",
    "/customers/?filter=paid_unknown", "/customers/?filter=no_expiry",
    "/customers/?filter=pending_install", "/customers/?filter=lapsed_offline",
    "/customers/?filter=suspended", "/customers/?filter=inactive",
    "/customers/?filter=pulled_out", "/customers/?filter=unclassified",
    "/customers/?filter=bogusvalue",
    "/customers/?search=delacruz",
    "/customers/?filter=active",          # legacy bookmark, must not 500
    "/customers/?filter=expired",         # legacy
    "/customers/?filter=inactive",        # legacy
    "/customers/?filter=no_expiration",   # legacy
    "/customers/?filter=paid_but_offline",# legacy
    "/add-customer/", "/subscriptions/", "/internet-plans/", "/plans/",
    "/payments/", "/logs/payments/", "/payment-logs/",
    "/agents/", "/cignal-dashboard/", "/cignal/",
    "/devices/devices/", "/devices/devices/%d/" % did,
    "/devices/devices/%d/sync/" % did,
    "/settings/", "/settings/import/", "/settings/users/",
    "/analytics/", "/reports/", "/audit-log/",
    "/customers/%d/" % cid, "/customers/view/%d/" % cid,
    "/api/notifications/", "/api/online-staff/",
    "/api/dashboard/customers/", "/api/dashboard/customers/?status_filter=active",
    "/api/dashboard/customers/?connection_filter=Not%20Connected",
    "/live-monitoring/", "/dispatch/", "/dispatch/queue/",
]

lines = ["CURATED SMOKE TEST", ""]
bad = []
slow = []

for url in PAGES:
    req = rf.get(url)
    req.user = su
    t0 = time.time()
    try:
        # Use the resolver so URL names map to views correctly.
        from django.urls import resolve, Resolver404
        try:
            m = resolve(url)
        except Resolver404:
            lines.append("  %-58s NO-ROUTE" % url[:58])
            continue
        resp = m.func(req, *m.args, **m.kwargs)
        code = getattr(resp, "status_code", 0)
        dt = time.time() - t0
        flag = ""
        if code >= 500:
            flag = "  <<<< 5xx"
            bad.append((url, code))
        elif code == 0:
            flag = "  <<<< no status_code"
            bad.append((url, "0"))
        if dt > 8:
            flag += "  <<<< SLOW %.1fs" % dt
            slow.append((url, dt))
        lines.append("  %-58s %s  %.1fs%s" % (url[:58], code, dt, flag))
    except Exception as e:
        dt = time.time() - t0
        lines.append("  %-58s EXC %s: %s  %.1fs  <<<< PROBLEM" % (
            url[:58], type(e).__name__, str(e)[:70], dt))
        bad.append((url, type(e).__name__))

lines.append("")
lines.append("PAGES=%d  PROBLEMS=%d  SLOW=%d" % (len(PAGES), len(bad), len(slow)))
if bad:
    lines.append("")
    lines.append("PROBLEM URLS:")
    for u, c in bad:
        lines.append("   %s -> %s" % (u, c))
open("/app/smoke2.txt", "w").write("\n".join(lines))
print("PROBLEMS=%d SLOW=%d of %d" % (len(bad), len(slow), len(PAGES)))
