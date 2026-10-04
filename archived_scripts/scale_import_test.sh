#!/bin/bash
# Import 2,041 subscribers for real and watch the container's memory while it runs.
# Self-contained: pulls the source dump in itself so a container recreate
# (which wipes /tmp) cannot break it.
set -e
cd /root/GAMETECH-BILLING-SYSTEM

LEGACY_HOST=/root/wip/legacy.sql

echo "=== 0. BACKUP ==="
TS=$(date +%Y%m%d_%H%M%S)
OUT=/root/backups/PRE_SCALE_${TS}.dump
docker exec gametech-db pg_dump -U gametech_user -Fc gametech_db > "$OUT"
ls -la "$OUT"

echo
echo "=== 1. STAGE THE SOURCE DUMP + BUILDER ==="
[ -f "$LEGACY_HOST" ] || cp /root/backups/backup-2026-03-20_06-21-43.sql "$LEGACY_HOST"
docker cp "$LEGACY_HOST" gametech-web:/tmp/legacy.sql
docker cp /root/wip/bsd.py gametech-web:/app/bsd.py
docker exec gametech-web ls -la /tmp/legacy.sql

echo
echo "=== 2. BUILD THE 2,041-ROW DUMP ==="
docker exec -i gametech-web python manage.py shell < /root/wip/bsd.py 2>&1 | tail -8
docker exec gametech-web ls -la /tmp/scale_2041.sql

echo
echo "=== 3. HOST MEMORY BEFORE ==="
free -m | head -2

echo
echo "=== 4. IMPORT WITH LIVE MEMORY WATCHING ==="
rm -f /tmp/mem_watch.txt
( for i in $(seq 1 400); do
    docker stats --no-stream --format '{{.MemUsage}}|{{.MemPerc}}' \
      gametech-web 2>/dev/null >> /tmp/mem_watch.txt
    sleep 3
  done ) &
WATCH=$!

START=$(date +%s)
docker exec gametech-web python manage.py import_legacy_customers \
  /tmp/scale_2041.sql 2>&1 | tail -28
END=$(date +%s)

kill $WATCH 2>/dev/null || true
sleep 1

echo
echo "=== 5. TIMING AND PEAK MEMORY ==="
echo "import wall clock : $((END-START)) seconds"
echo "peak container mem:"
sort -t'|' -k2 -r /tmp/mem_watch.txt 2>/dev/null | head -3
rm -f /tmp/mem_watch.txt
echo "host memory after:"
free -m | head -2

echo
echo "=== 6. POST-IMPORT STATE ==="
docker exec gametech-web python manage.py shell -c "
from billing.models import Customer, Payment
print('customers:', Customer.objects.count())
print('payments :', Payment.objects.count())
" 2>&1 | tail -3