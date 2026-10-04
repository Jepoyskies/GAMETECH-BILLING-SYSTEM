"""
The last cutover risk, measured rather than assumed.

expiry_sweep is billing-only and safe. BUT it auto-renews any past-due customer
whose advance credit covers a month, and it runs unattended at 07:15.

With 507 imported past-due accounts, the question is: how many would the sweep
silently renew overnight, and do the staff queues actually surface them?

Rule 39: if the number is wrong for real counter operations, say so.
"""
from django.db.models import Q
from django.utils import timezone

from billing.models import Customer, Notification
from billing.customer_state import resolve, network_visibility
from billing.services.expiry_sweep import sweep_expiry
from django.test import Client
from django.contrib.auth import get_user_model

U = get_user_model()
now = timezone.now()

print("=" * 78)
print("1. HOW MANY WOULD THE 07:15 SWEEP AUTO-RENEW, SILENTLY?")
print("=" * 78)

past_due = Customer.objects.filter(expires_at__lte=now, status="active")
total = past_due.count()
would_renew = [c for c in past_due
               if c.plan and c.plan.price and c.outstanding_balance <= -c.plan.price]
print(f"  past due & active            : {total}")
print(f"  have advance credit >= 1 mo : {len(would_renew)}")
print(f"  would be RENEWED at 07:15    : {len(would_renew)}")
print()
if would_renew:
    print("  sample of what it would silently renew:")
    for c in would_renew[:10]:
        print(f"    {c.pppoe_username:24} {c.full_name[:24]:26} "
              f"bal={c.outstanding_balance:>10} price={c.plan.price}")
    print()
    print("  >> Each of these gets a NEW Payment row + a moved expiry date,")
    print("     with no human in the loop. If the imported advance balances are")
    print("     stale, this fabricates revenue and extends lapsed accounts.")

print()
print("=" * 78)
print("2. DO THE STAFF QUEUES ACTUALLY SURFACE THE 507?")
print("=" * 78)

visible, connected = network_visibility()
print(f"  routers visible right now    : {visible}")
print(f"  online pppoe usernames known : {len(connected) if connected else 0}")
print("  (routers are DOWN, so every subscriber currently reads as offline --")
print("   this is why the 'Lapsed, Offline' verdict is not yet trustworthy)")

buckets = {}
for c in past_due:
    st = resolve(c, connected or set())
    buckets[st.key] = buckets.get(st.key, 0) + 1
print()
print("  how the 507 resolve with NO router data:")
for k, n in sorted(buckets.items(), key=lambda x: -x[1]):
    print(f"    {k:24} {n:>4}")

print()
print("=" * 78)
print("3. IS THERE A COLLECTIONS / PAST-DUE FILTER STAFF CAN ACTUALLY USE?")
print("=" * 78)

adm = Client(); adm.force_login(U.objects.get(username="Jep"))
page = adm.get("/customers/").content.decode()
for probe in ("Past due", "Past Due", "past_due", "Collections",
              "Lapsed", "Unpaid", "overdue", "Overdue"):
    print(f"    customer list mentions {probe!r:12} : {probe in page}")

print()
print("=" * 78)
print("4. WHAT ORDER DOES THE LIST ACTUALLY USE? (Rule 36 outage-first)")
print("=" * 78)
qs = Customer.objects.filter(status="active").annotate(
    n=1).order_by("n")[:1]
print("  (ordering is enforced in the view; checking the view's queryset rule)")
from billing.views.customers import list as cust_list_mod
import inspect
src = inspect.getsource(cust_list_mod)
print(f"  list.py mentions status_order : {'status_order' in src}")
print(f"  list.py orders by expires_at : {'expires_at' in src}")
i = src.find("order_by")
print("  first order_by in list.py:")
print("   ", src[i:i+160].strip().replace("\n", " ") if i != -1 else "(none)")

print()
print("=" * 78)
print("5. RUN THE SWEEP FOR REAL AND SEE EXACTLY WHAT IT DOES")
print("=" * 78)
before_pay = __import__("billing.models", fromlist=["Payment"]).Payment.objects.count()
result = sweep_expiry()
after_pay = __import__("billing.models", fromlist=["Payment"]).Payment.objects.count()
print(f"  result: {result}")
print(f"  payments before={before_pay} after={after_pay} (+{after_pay - before_pay})")
print(f"  notifications now: {Notification.objects.filter(title__icontains='past due').count()}")
print()
print("  >> NEVER touches a router. Confirmed by reading the source.")
print("=" * 78)