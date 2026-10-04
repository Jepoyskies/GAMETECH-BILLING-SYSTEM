"""Before flipping ROUTER_MODE=live, prove that NO scheduled Celery task can
write to a router unattended. This is the safety gate for going live."""
import inspect

from django.conf import settings
from django.apps import apps
from django.utils import timezone

print("=" * 76)
print("SCHEDULED TASKS")
print("=" * 76)
sched = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
for name, entry in sched.items():
    print(f"  {name:38} {entry.get('task')}  {entry.get('schedule')}")

# Router-writing verbs we refuse to see on a timer.
WRITE_HINTS = (
    "add_pppoe_user", "delete_pppoe_user", "set_pppoe_comment",
    "suspend_pppoe_user", "enable_pppoe_user", "set_user_pppoe_profile",
    "kick_active_user", "remove_active_pppoe_user", "sync_customer_to_mikrotik",
    "sync_plans", "push",
)


def task_sources():
    from billing import tasks as billing_tasks
    mod = None
    try:
        import billing.tasks as m
        mod = m
    except Exception:
        pass
    return mod


mod = task_sources()
print()
print("=" * 76)
print("DOES ANY SCHEDULED TASK CALL A ROUTER-WRITE METHOD?")
print("=" * 76)
danger = []
if mod:
    for name, entry in sched.items():
        path = entry.get("task", "")
        fname = path.split(".")[-1]
        fn = getattr(mod, fname, None)
        if fn is None:
            print(f"  {name:38} -> {path} (task not found in billing.tasks)")
            continue
        try:
            src = inspect.getsource(fn)
        except Exception:
            print(f"  {name:38} -> could not read source")
            continue
        hits = [h for h in WRITE_HINTS if h in src]
        print(f"  {name:38} router-writes: {hits if hits else 'NONE'}")
        if hits:
            danger.append((name, hits))

print()
print("=" * 76)
print("SAFETY VERDICT")
print("=" * 76)
if danger:
    print("  UNSAFE -- these scheduled tasks can write to routers:")
    for n, h in danger:
        print(f"    {n}: {h}")
else:
    print("  SAFE -- no scheduled task performs a router write.")
    print("  Router writes only happen when a staff member acts in the Sync Manager.")

print()
print(f"  ROUTER_MODE currently: {getattr(settings, 'ROUTER_MODE', '?')}")