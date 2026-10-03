import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gametech_core.settings")
django.setup()

from django.conf import settings
from billing.models import Customer
from billing.customer_state import is_router_unlinked, LIFECYCLES, FILTERS
from network_manager import sync_helpers

print("=== DEPLOY VERIFICATION (read-only) ===")
print("ROUTER_MODE          :", settings.ROUTER_MODE)
print("django               :", django.get_version())
print()

# Defect 1: the disabled-string normalisation must exist in the shipped view.
from network_manager.views import sync as sync_view
import inspect
src = inspect.getsource(sync_view)
print("DEFECT 1  disabled-string normalised :",
      '"true", "yes", "1"' in src or "'true', 'yes', '1'" in src)
print("DEFECT 1  old bool() removed          :",
      "bool(ru.get('disabled'))" not in src)
print()

# Defect 2: every writer goes through the single comment builder.
print("DEFECT 2  canonical comment used     :", src.count("build_router_comment("))
print("DEFECT 2  bare-name comment gone     :", "comment=customer.full_name" not in src)
print()

# Defect 3/4: approvals recorded and routers assigned.
print("DEFECT 3  mark_synced called         :", src.count("mark_synced("))
print("DEFECT 4  autofix links router       :", "mark_synced(customer, device, request.user)" in src)
print()

# New lifecycle present.
print("NEW  unlinked lifecycle registered  :", "unlinked" in LIFECYCLES)
print("NEW  unlinked filter pill present   :", any(k == "unlinked" for k, _, _, _ in FILTERS))
print("NEW  unlinked priority              :", LIFECYCLES["unlinked"].priority)
print()

# Live data: how many accounts the bouncer would now queue.
unlinked = Customer.objects.filter(mikrotik_device__isnull=True).exclude(
    pppoe_username__isnull=True).exclude(pppoe_username="").count()
unverified = Customer.objects.filter(
    sync_status__in=("Unverified", "Blocked")).exclude(
    pppoe_username="").count()
print("=== WHAT THE BOUNCER NOW QUEUES ===")
print("accounts with no router assigned   :", unlinked)
print("accounts Unverified or Blocked     :", unverified)
print()

juan = Customer.objects.filter(pppoe_username="delacruz_juan").first()
if juan:
    print("=== JUAN DELA CRUZ (id 46) ===")
    print("mikrotik_device :", juan.mikrotik_device)
    print("sync_status     :", juan.sync_status)
    print("unlinked        :", is_router_unlinked(juan))
    print("needs approval  :", sync_helpers.account_needs_approval(juan))
    print("reasons         :", sync_helpers.approval_reasons(juan))
    print("comment if approved:", sync_helpers.build_router_comment(juan))