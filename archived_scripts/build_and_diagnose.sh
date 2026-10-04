#!/bin/bash
# Build the scale dump, persist it to the HOST (container /tmp does not survive
# a recreate), then diagnose why 2,041 rows became ~288 customers.
set -e
cd /root/GAMETECH-BILLING-SYSTEM

echo "=== 1. stage source + builder ==="
cp -n /root/backups/backup-2026-03-20_06-21-43.sql /root/wip/legacy.sql || true
docker cp /root/wip/legacy.sql gametech-web:/tmp/legacy.sql
docker cp /root/wip/bsd.py gametech-web:/app/bsd.py

echo "=== 2. build ==="
docker exec -i gametech-web python manage.py shell < /root/wip/bsd.py 2>&1 | tail -6

echo "=== 3. persist the scale dump to the HOST ==="
docker cp gametech-web:/tmp/scale_2041.sql /root/wip/scale_2041.sql
ls -la /root/wip/scale_2041.sql

echo "=== 4. diagnose ==="
docker cp /root/wip/scale_2041.sql gametech-web:/tmp/scale_2041.sql
docker cp /root/wip/did.py gametech-web:/app/did.py
docker exec -i gametech-web python manage.py shell < /root/wip/did.py 2>&1 | tail -60