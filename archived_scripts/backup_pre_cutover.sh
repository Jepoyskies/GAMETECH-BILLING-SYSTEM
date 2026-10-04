#!/bin/bash
set -e
TS=$(date +%Y%m%d_%H%M%S)
OUT=/root/backups/PRE_CUTOVER_${TS}.dump
docker exec gametech-db pg_dump -U gametech_user -Fc gametech_db > "$OUT"
ls -la "$OUT"
docker cp "$OUT" gametech-db:/tmp/v.dump
echo "--- verify ---"
docker exec gametech-db pg_restore -l /tmp/v.dump | grep -c "TABLE DATA"
docker exec gametech-db pg_restore -l /tmp/v.dump | grep "TABLE DATA public billing_customer "
docker exec gametech-db rm -f /tmp/v.dump
echo "VERIFIED"