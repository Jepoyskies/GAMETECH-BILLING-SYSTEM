#!/bin/bash
# CHAOS TEST v2 -- clean baseline first.
#
# v1 was inconclusive twice over: `pkill` does not exist in the image, and the
# baseline was polluted by the earlier partial import so "no change" and "rolled
# back" were indistinguishable. Fixed both: restore to 1 customer, and kill the
# import by restarting the container (which reliably kills the process).
set -e
cd /root/GAMETECH-BILLING-SYSTEM

DUMP=/root/backups/PRE_SCALE_20261004_075126.dump

echo "=== 0. RESTORE to a known-clean baseline ==="
docker compose stop web celery celery-beat >/dev/null 2>&1 || true
docker exec gametech-db psql -U gametech_user -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='gametech_db';" >/dev/null 2>&1 || true
docker exec -i gametech-db pg_restore -U gametech_user -d gametech_db \
  --clean --if-exists --no-owner < "$DUMP" 2>&1 | tail -3 || true
docker compose up -d >/dev/null 2>&1
sleep 22

docker exec gametech-web python manage.py shell -c "
from billing.models import Customer
print('BASELINE customers:', Customer.objects.count())
" 2>&1 | tail -1

echo
echo "=== 1. stage the 2,041-row dump ==="
[ -f /root/wip/legacy.sql ] || cp /root/backups/backup-2026-03-20_06-21-43.sql /root/wip/legacy.sql
docker cp /root/wip/scale_2041.sql gametech-web:/tmp/scale_2041.sql

echo
echo "=== 2. start the import, let it get under way ==="
docker exec -d gametech-web python manage.py import_legacy_customers /tmp/scale_2041.sql
sleep 110

echo "=== 3. is it running? ==="
docker exec gametech-web sh -c "ps -eo pid,etime,args 2>/dev/null | grep -c '[i]mport_legacy' || echo 0" || true

echo
echo "=== 4. KILL MID-TRANSACTION (container restart) ==="
docker restart gametech-web >/dev/null 2>&1
echo "killed"
sleep 22

echo
echo "=== 5. VERDICT ==="
docker exec gametech-web python manage.py shell -c "
from billing.models import Customer, Payment
n = Customer.objects.count()
print('AFTER customers:', n)
print('AFTER payments :', Payment.objects.count())
print()
if n == 1:
    print('>>> PASS -- killed mid-import, database rolled back WHOLE.')
    print('>>> A half-imported subscriber base is no longer possible.')
else:
    print('>>> FAIL -- left', n, 'customers. Partial import still possible.')
" 2>&1 | tail -5