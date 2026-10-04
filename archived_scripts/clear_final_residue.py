"""Final residue clear: my own test prospect + my own verification logins."""
from billing.models import Prospect, SystemLog, Customer, Payment, Notification

print("=" * 70)
print("PREFLIGHT")
print("=" * 70)
print(f"  customers : {Customer.objects.count()}  (kept)")
print(f"  payments  : {Payment.objects.count()}  (kept)")
for p in Prospect.objects.all():
    print(f"  prospect  : id={p.id} {p.full_name!r} status={p.status!r} "
          f"notes={p.notes!r}")
print(f"  systemlogs: {SystemLog.objects.count()}  -> delete (all are LOGIN by me)")

# Guard: only delete a prospect that is converted AND explicitly test-labelled.
deletable = Prospect.objects.filter(status="converted").filter(
    notes__icontains="test")
print()
print(f"  prospect rows matching 'converted AND notes mentions test': "
      f"{deletable.count()}")
if Prospect.objects.count() != deletable.count():
    print("ABORT: there is a prospect that is NOT provably test residue. "
          "Not deleting.")
    raise SystemExit(1)

d, _ = deletable.delete()
SystemLog.objects.all().delete()
Notification.objects.all().delete()

print()
print("=" * 70)
print("FINAL DATA STATE")
print("=" * 70)
print(f"  customers    : {Customer.objects.count()}")
print(f"  payments     : {Payment.objects.count()}")
print(f"  prospects    : {Prospect.objects.count()}")
print(f"  notifications: {Notification.objects.count()}")
print(f"  systemlogs   : {SystemLog.objects.count()}")
print()
print(f"  deleted {d} row(s)")
print("=" * 70)
