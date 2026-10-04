#!/bin/bash
# Reproduce with the small 527-row file to capture the REAL traceback fast.
set -e
cd /root/GAMETECH-BILLING-SYSTEM

git pull origin main 2>&1 | tail -1
docker compose up -d >/dev/null 2>&1
sleep 20

cp -n /root/wip/legacy.sql /root/wip/legacy.sql 2>/dev/null || true
[ -f /root/wip/legacy.sql ] || cp /root/backups/backup-2026-03-20_06-21-43.sql /root/wip/legacy.sql
docker cp /root/wip/legacy.sql gametech-web:/tmp/legacy.sql

echo "=== customers before ==="
docker exec gametech-web python manage.py shell -c "
from billing.models import Customer; print(Customer.objects.count())" 2>&1 | tail -1

echo
echo "=== run, capturing EVERYTHING including the traceback ==="
docker exec gametech-web sh -c \
  "python manage.py import_legacy_customers /tmp/legacy.sql > /tmp/imp.log 2>&1; echo EXIT=\$?" || true
docker exec gametech-web sh -c \
  "grep -vE 'RuntimeWarning|warnings.warn' /tmp/imp.log | tail -40"

echo
echo "=== last 25 lines raw (traceback lives here) ==="
docker exec gametech-web tail -25 /tmp/imp.log

echo
echo "=== customers after ==="
docker exec gametech-web python manage.py shell -c "
from billing.models import Customer; print(Customer.objects.count())" 2>&1 | tail -1