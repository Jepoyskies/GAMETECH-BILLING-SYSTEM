"""Sections 4 and 5, redone after the annotate() typo killed them."""
import inspect
from billing.models import Notification, Payment
from billing.services.expiry_sweep import sweep_expiry

print("=" * 78)
print("4. WHAT ORDER DOES THE CUSTOMER LIST USE? (Rule 36 outage-first)")
print("=" * 78)
from billing.views.customers import list as cust_list_mod
src = inspect.getsource(cust_list_mod)
print(f"  list.py mentions status_order : {'status_order' in src}")
print(f"  list.py orders by expires_at : {'expires_at' in src}")
idx, shown = 0, 0
while shown < 4:
    i = src.find("order_by", idx)
    if i == -1:
        break
    print("   ", src[i:i+150].strip().replace("\n", " "))
    idx, shown = i + 1, shown + 1

print()
print("=" * 78)
print("5. RUN THE SWEEP FOR REAL")
print("=" * 78)
before_pay = Payment.objects.count()
before_notif = Notification.objects.count()
result = sweep_expiry()
after_pay = Payment.objects.count()
print(f"  result            : {result}")
print(f"  payments          : {before_pay} -> {after_pay} (+{after_pay - before_pay})")
print(f"  notifications     : {before_notif} -> {Notification.objects.count()}")
latest = Notification.objects.order_by("-id").first()
if latest:
    print(f"  notification title: {latest.title}")
    print(f"  notification body : {latest.message}")
print()
print("  >> Never calls the router. Confirmed by reading expiry_sweep.py.")
print("=" * 78)
