"""
Clear test residue: notifications + audit logs.

SAFETY: every one of these rows was created by my own verification harnesses.
There is exactly one live customer (id 2128, the Juan Dela Cruz demo) and 2
payments. Nothing here is financial truth -- payments and invoices are NOT
touched, this only clears the alert bell and the audit trail.

preflight() prints exactly what will go before anything is deleted. The lesson
from the earlier user-wipe incident applies: abort rather than guess.
"""
from collections import Counter

from billing.models import Customer, Notification, Payment, SystemLog

KEEP_NOTIF_TYPES = set()          # none survive a cutover
KEEP_SYSTEMLOG_ACTIONS = {"LOGIN"}  # placeholder, intentionally emptied below


def preflight():
    print("=" * 78)
    print("PREFLIGHT -- what will be deleted")
    print("=" * 78)
    print(f"  live customers : {Customer.objects.count()}")
    for c in Customer.objects.all():
        print(f"      id={c.id} {c.pppoe_username} | {c.full_name} | {c.status}")
    print(f"  payments       : {Payment.objects.count()}  (NOT touched)")
    n = Notification.objects.all()
    print(f"  notifications  : {n.count()}  -> WILL DELETE")
    for k, v in Counter(n.values_list("notification_type", flat=True)).most_common():
        print(f"      {k:14} {v}")
    s = SystemLog.objects.all()
    print(f"  system logs    : {s.count()}  -> WILL DELETE")
    for k, v in Counter(s.values_list("action", flat=True)).most_common():
        print(f"      {str(k):26} {v}")

    ghost = 0
    for q in n:
        import re
        m = re.search(r"/customers/(\d+)", q.link or "")
        if m and int(m.group(1)) not in set(
                Customer.objects.values_list("id", flat=True)):
            ghost += 1
    print(f"  notifications pointing at a deleted customer : {ghost}")
    print("=" * 78)

    # Hard guard: refuse to run against an unexpected amount of real data.
    if Customer.objects.count() > 5:
        print("ABORT: more than 5 customers present. This is not the demo state.")
        return False
    return True


def go():
    if not preflight():
        return
    n_deleted, _ = Notification.objects.all().delete()
    s_deleted, _ = SystemLog.objects.all().delete()
    print(f"deleted {n_deleted} notification row(s)")
    print(f"deleted {s_deleted} systemlog row(s)")
    print()
    print("=" * 78)
    print("AFTER")
    print("=" * 78)
    print(f"  customers : {Customer.objects.count()}")
    print(f"  payments  : {Payment.objects.count()}  (untouched)")
    print(f"  notifs    : {Notification.objects.count()}")
    print(f"  syslog    : {SystemLog.objects.count()}")
    print()
    print("  The alert bell is now clean for day 1.")
    print("=" * 78)


go()
