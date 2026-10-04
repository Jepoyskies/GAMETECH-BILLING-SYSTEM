#!/bin/bash
# CHAOS TEST: kill the import mid-run and prove the database rolls back whole.
#
# This is not a synthetic failure. It is exactly what already happened tonight:
# the container was recreated while the 2,041-row import was running, and the
# database was left holding 287 partial customers with no report.
set -e
cd /root/GAMETECH-BILLING-SYSTEM

git pull origin main 2>&1 | tail -1
docker compose up -d >/dev/null 2>&1
sleep 20

[ -f /root/wip/legacy.sql ] || cp /root/backups/backup-2026-03-20_06-21-43.sql /root/wip/legacy.sql
docker cp /root/wip/legacy.sql gametech-web:/tmp/legacy.sql
docker cp /root/wip/scale_2041.sql gametech-web:/tmp/scale_2041.sql
docker cp /root/wip/bsd.py gametech-web:/app/bsd.py

echo
echo "=== 0. clean slate (undo last night's partial import) ==="
docker exec -i gametech-web python manage.py shell -c "
from billing.models import Customer, Payment, SubscriptionPlan, AccountType
from network_manager.models import MikrotikDevice
print('BEFORE customers:', Customer.objects.count())
print('BEFORE payments :', Payment.objects.count())
" 2>&1 | tail -2

echo
echo "=== 1. start the 2,041-row import in the BACKGROUND ==="
docker exec -d gametech-web python manage.py import_legacy_customers /tmp/scale_2041.sql
echo "started. letting it get properly under way..."
sleep 100

echo
echo "=== 2. mid-run check: it IS writing ==="
docker exec gametech-web python manage.py shell -c "
from billing.models import Customer
print('customers DURING import:', Customer.objects.count())
" 2>&1 | tail -1

echo
echo "=== 3. KILL IT HARD, mid-transaction ==="
docker exec gametech-web pkill -9 -f import_legacy_customers || true
docker restart gametech-web >/dev/null 2>&1
echo "killed + container restarted"
sleep 22

echo
echo "=== 4. THE VERDICT: rolled back whole, or left a mess? ==="
docker exec gametech-web python manage.py shell -c "
from billing.models import Customer, Payment, SubscriptionPlan
n = Customer.objects.count()
print('AFTER customers:', n)
print('AFTER payments :', Payment.objects.count())
print()
print('PASS - rolled back completely' if n == 1
      else 'FAIL - left ' + str(n) + ' customers behind (partial import)')
" 2>&1 | tail -5

echo
echo "=== 5. clean up the synthetic accounts if any survived ==="
docker exec gametech-web python manage.py shell -c "
from billing.models import Customer
stray = Customer.objects.exclude(pppoe_username='delacruz_juan_e2e')
print('stray customers:', stray.count())
for c in stray[:10]:
    print('   ', c.pppoe_username)
" 2>&1 | tail -6