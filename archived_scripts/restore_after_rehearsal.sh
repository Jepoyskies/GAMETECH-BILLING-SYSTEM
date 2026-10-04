#!/bin/bash
# Restore the clean pre-rehearsal state. The rehearsal import was a drill.
set -e
DUMP=/root/backups/PRE_REHEARSAL_20261004_064849.dump

cd /root/GAMETECH-BILLING-SYSTEM

echo "=== stop the apps so nothing writes during the restore ==="
docker compose stop web celery celery-beat 2>&1 | tail -3

echo
echo "=== drop lingering connections ==="
docker exec gametech-db psql -U gametech_user -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='gametech_db';" >/dev/null

echo "=== restore ==="
docker exec -i gametech-db pg_restore -U gametech_user -d gametech_db --clean --if-exists --no-owner < "$DUMP" 2>&1 | tail -5

echo
echo "=== bring everything back up ==="
docker compose up -d 2>&1 | tail -3
sleep 22

echo
echo "=== verify the rehearsal is gone ==="
docker exec gametech-web python manage.py shell -c "
from billing.models import Customer, Payment, Notification
print('customers :', Customer.objects.count())
print('payments  :', Payment.objects.count())
print('notifs    :', Notification.objects.count())
for c in Customer.objects.all():
    print('  ->', c.pppoe_username, '|', c.full_name, '|', c.status)
" 2>&1 | tail -8