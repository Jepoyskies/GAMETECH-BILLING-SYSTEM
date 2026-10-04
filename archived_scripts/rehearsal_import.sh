#!/bin/bash
# FULL CUTOVER REHEARSAL: actually import for real, verify the thing the owner
# is most afraid of (expiry dates landing correctly), measure the past-due
# backlog, then restore the clean state.
set -e
cd /root/GAMETECH-BILLING-SYSTEM

TS=$(date +%Y%m%d_%H%M%S)
OUT=/root/backups/PRE_REHEARSAL_${TS}.dump
echo "=== 0. BACKUP BEFORE THE REHEARSAL ==="
docker exec gametech-db pg_dump -U gametech_user -Fc gametech_db > "$OUT"
ls -la "$OUT"

echo
echo "=== 1. REAL IMPORT (not dry-run) ==="
docker cp /root/backups/backup-2026-03-20_06-21-43.sql gametech-web:/tmp/legacy.sql
docker exec gametech-web python manage.py import_legacy_customers /tmp/legacy.sql 2>&1 | tail -20