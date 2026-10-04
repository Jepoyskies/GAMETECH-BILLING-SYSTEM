from collections import Counter
from billing.models import Notification, Customer, Payment, SystemLog

print("=" * 78)
print("NOTIFICATION INVENTORY (is any of this worth keeping?)")
print("=" * 78)
qs = Notification.objects.all().order_by("-id")
print(f"total: {qs.count()}\n")
print("by type:")
for k, n in Counter(q.notification_type for q in qs).most_common():
    print(f"  {k:16} {n}")
print("\nnewest 8:")
for q in qs[:8]:
    print(f"  [{q.notification_type:10}] {q.title[:70]}")
print()
print("referencing a customer that still exists:")
live = set(Customer.objects.values_list("id", flat=True))
print(f"  live customer ids: {sorted(live)}")
print()
print("=" * 78)
print("SYSTEM LOG / AUDIT INVENTORY")
print("=" * 78)
print(f"SystemLog rows: {SystemLog.objects.count()}")
for k, n in Counter(SystemLog.objects.values_list("action", flat=True)).most_common(8):
    print(f"  {str(k):26} {n}")
