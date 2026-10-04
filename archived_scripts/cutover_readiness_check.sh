#!/bin/bash
# Readiness checklist for the cutover. Read-only. Run this BEFORE disconnecting
# the old system.
set -u
cd /root/GAMETECH-BILLING-SYSTEM

echo "=============================================================="
echo " 1. CONTAINERS"
echo "=============================================================="
docker ps --format '{{.Names}}\t{{.Status}}'

echo
echo "=============================================================="
echo " 2. DJANGO HEALTH"
echo "=============================================================="
docker exec gametech-web python manage.py check 2>&1 | tail -2
docker exec gametech-web python manage.py migrate --check >/dev/null 2>&1 \
  && echo "migrations: UP TO DATE" || echo "migrations: PENDING -- RUN MIGRATE"

echo
echo "=============================================================="
echo " 3. RUNTIME FLAGS"
echo "=============================================================="
docker exec gametech-web printenv | grep -E 'ROUTER_MODE|INCENTIVES|SESSION_COOKIE_AGE'

echo
echo "=============================================================="
echo " 4. ROUTER REACHABILITY (the 3 real routers)"
echo "=============================================================="
docker exec -i gametech-web python manage.py shell <<'PY'
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI
for d in MikrotikDevice.objects.all():
    try:
        n = len(MikrotikAPI(d)._get_api().get_resource("/ppp/secret").get() or [])
        print(f"  {d.device_name:26} {d.ip_address:16} OK   {n} secrets")
    except Exception as e:
        print(f"  {d.device_name:26} {d.ip_address:16} DOWN {type(e).__name__}")
PY

echo
echo "=============================================================="
echo " 5. SAFETY: does any scheduled task write to a router?"
echo "=============================================================="
docker exec gametech-web python manage.py shell <<'PY'
import inspect
from django.conf import settings
import billing.tasks as t
sched = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
WRITES = ("add_pppoe_user","delete_pppoe_user","suspend_pppoe_user",
          "enable_pppoe_user","set_user_pppoe_profile","kick_active_user",
          "sync_customer_to_mikrotik")
bad = []
for name, e in sched.items():
    fn = getattr(t, e.get("task","").split(".")[-1], None)
    if fn is None: continue
    src = inspect.getsource(fn)
    hits = [w for w in WRITES if w in src]
    print(f"  {name:28} router-writes: {hits or 'NONE'}")
    if hits: bad.append(name)
print()
print("  VERDICT:", "UNSAFE "+str(bad) if bad else "SAFE - no unattended router writes")
PY

echo
echo "=============================================================="
echo " 6. SCHEDULED JOBS"
echo "=============================================================="
docker exec gametech-web python manage.py shell <<'PY'
from django.conf import settings
for n, e in getattr(settings, "CELERY_BEAT_SCHEDULE", {}).items():
    print(f"  {n:28} {e.get('schedule')}")
PY

echo
echo "=============================================================="
echo " 7. CURRENT DATA"
echo "=============================================================="
docker exec gametech-web python manage.py shell <<'PY'
from billing.models import Customer, Payment
from dispatch.models import JobTicket
print(f"  customers: {Customer.objects.count()}  payments: {Payment.objects.count()}  tickets: {JobTicket.objects.count()}")
PY

echo
echo "=============================================================="
echo " 8. RECENT 5xx"
echo "=============================================================="
docker logs --since 2h gametech-web 2>&1 | grep -cE '" 5[0-9][0-9] ' || true

echo
echo "=============================================================="
echo " 9. BACKUP ON DISK"
echo "=============================================================="
ls -la /root/backups/*.dump /root/backups/*.sql 2>/dev/null | tail -4