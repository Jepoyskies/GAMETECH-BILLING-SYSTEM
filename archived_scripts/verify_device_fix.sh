#!/bin/bash
# Prove the IP-matching fix: the dump calls the router "ccr2116.v1", staff
# registered it as "ccr2116.v1 - patag". After the fix, imported customers must
# land on the REAL device and no phantom row may be created.
set -e
cd /root/GAMETECH-BILLING-SYSTEM

git pull origin main 2>&1 | tail -1
docker compose up -d --force-recreate web >/dev/null 2>&1
sleep 22

[ -f /root/wip/legacy.sql ] || cp /root/backups/backup-2026-03-20_06-21-43.sql /root/wip/legacy.sql
docker cp /root/wip/legacy.sql gametech-web:/tmp/legacy.sql

echo
echo "=== 0. RESET: drop the scale-test rows and the phantom device ==="
docker cp /root/wip/reset.py gametech-web:/app/reset.py
docker exec -i gametech-web python manage.py shell < /root/wip/reset.py 2>&1 | tail -14

echo
echo "=== 1. run the 527-row import (its device_name is 'ccr2116.v1') ==="
docker exec gametech-web sh -c \
  "python manage.py import_legacy_customers /tmp/legacy.sql > /tmp/i2.log 2>&1; echo EXIT=\$? >> /tmp/i2.log"
docker exec gametech-web grep -E "EXIT=|Import complete|Devices ready" /tmp/i2.log || true

echo
echo "=== 2. VERIFY device assignment ==="
docker cp /root/wip/vd.py gametech-web:/app/vd.py
docker exec -i gametech-web python manage.py shell < /root/wip/vd.py 2>&1 | tail -30