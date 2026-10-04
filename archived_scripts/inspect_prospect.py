from billing.models import Prospect, SystemLog

print("=" * 70)
print("PROSPECT IN THE DATABASE")
print("=" * 70)
for p in Prospect.objects.all():
    print(f"  id={p.id} name={p.full_name!r} phone={getattr(p,'phone','-')!r} "
          f"status={getattr(p,'status','-')!r}")
    for f in ("created_at", "created_by", "notes", "barangay", "plan"):
        if hasattr(p, f):
            v = getattr(p, f)
            print(f"      {f:12} = {v!r}")
print()
print("=" * 70)
print("SYSTEM LOG ROWS (mine, from the verification logins)")
print("=" * 70)
for s in SystemLog.objects.all():
    print(f"  {s.action:24} by={s.changed_by!r:26} target={s.target_name!r}")
print()
print("=" * 70)
print("VERDICT")
print("=" * 70)
print(f"  prospects to delete: {Prospect.objects.count()}")
print(f"  systemlogs to delete: {SystemLog.objects.count()}")
