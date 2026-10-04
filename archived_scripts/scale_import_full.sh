#!/bin/bash
# The real deliverable: a 2,041-row import that COMPLETES, timed and
# memory-watched, under the new all-or-nothing wrapper.
set -e
cd /root/GAMETECH-BILLING-SYSTEM

TS=$(date +%Y%m%d_%H%M%S)
echo "=== 0. BACKUP ==="
docker exec gametech-db pg_dump -U gametech_user -Fc gametech_db \
  > /root/backups/PRE_SCALE_RUN_${TS}.dump
ls -la /root/backups/PRE_SCALE_RUN_${TS}.dump

echo
echo "=== 1. stage ==="
[ -f /root/wip/legacy.sql ] || cp /root/backups/backup-2026-03-20_06-21-43.sql /root/wip/legacy.sql
docker cp /root/wip/legacy.sql gametech-web:/tmp/legacy.sql
docker cp /root/wip/scale_2041.sql gametech-web:/tmp/scale_2041.sql
docker exec gametech-web ls -la /tmp/scale_2041.sql

echo
echo "=== 2. host memory before ==="
free -m | head -2

echo
echo "=== 3. FULL IMPORT, timed, memory watched ==="
rm -f /tmp/mem_watch.txt
( for i in $(seq 1 400); do
    docker stats --no-stream --format '{{.MemUsage}}|{{.MemPerc}}' \
      gametech-web 2>/dev/null >> /tmp/mem_watch.txt
    sleep 3
  done ) &
WATCH=$!

START=$(date +%s)
docker exec gametech-web python manage.py import_legacy_customers \
  /tmp/scale_2041.sql 2>&1 | grep -vE "RuntimeWarning|warnings.warn|^$" | tail -30
END=$(date +%s)

kill $WATCH 2>/dev/null || true
sleep 1

echo
echo "=== 4. TIMING AND PEAK MEMORY ==="
echo "import wall clock : $((END-START)) seconds"
echo "peak container mem:"
sort -t'|' -k2 -r /tmp/mem_watch.txt 2>/dev/null | head -2
rm -f /tmp/mem_watch.txt
free -m | head -2