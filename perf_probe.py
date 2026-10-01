"""Where do the 40 seconds on /customers/ actually go?

Splits the view into: query+resolve, then template render.
"""
import time

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory

from billing.models import Customer
from billing.customer_state import annotate, network_visibility
from billing.views.customers.list import customer_list

User = get_user_model()
rf = RequestFactory()
su = User.objects.filter(is_superuser=True).first()

# --- 1. data layer only -------------------------------------------------
t0 = time.time()
rows = list(Customer.objects.select_related("plan", "agent", "barangay", "mikrotik_device")
            .exclude(status="closed_not_installed"))
t_query = time.time() - t0

t0 = time.time()
vis, conn = network_visibility()
rows = annotate(rows, conn)
for c in rows:
    c.is_paid_offline = c.lifecycle.key == "paid_offline"
    c.is_connected_unpaid = c.lifecycle.key == "connected_unpaid"
    c.is_no_expiry = c.lifecycle.key == "no_expiry"
    c.status_order = c.lifecycle.priority
t_resolve = time.time() - t0

# --- 2. per-row property cost (what the template calls) -----------------
t0 = time.time()
for c in rows:
    c.router_status
    c.connection_status
t_props = time.time() - t0

# --- 3. full view -------------------------------------------------------
req = rf.get("/customers/")
req.user = su
t0 = time.time()
resp = customer_list(req)
t_view = time.time() - t0
html = resp.content.decode("utf-8")

out = [
    "rows            : %d" % len(rows),
    "query           : %.2fs" % t_query,
    "resolve         : %.2fs" % t_resolve,
    "row properties  : %.2fs   <- router_status + connection_status" % t_props,
    "FULL VIEW       : %.2fs" % t_view,
    "html size       : %.1f MB" % (len(html) / 1024 / 1024),
    "bytes per row   : %d" % (len(html) // max(len(rows), 1)),
    "",
    "So the template render (view total minus the data layer) is about %.2fs" % (
        t_view - t_query - t_resolve - t_props),
]
open("/app/perf.txt", "w").write("\n".join(out))
print("\n".join(out))
