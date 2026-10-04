#!/bin/bash
# Flip ROUTER_MODE to live. Safety preconditions already verified:
#   - no scheduled Celery task performs a router write (check_scheduled_router_writes.py)
#   - writes only happen when a staff member acts in the Sync Manager
#   - sync_push_user is gated to Admin/Editor/CSR
set -e
ENV=/root/GAMETECH-BILLING-SYSTEM/.env

cp "$ENV" "$ENV.bak.pre-live-$(date +%Y%m%d_%H%M%S)"

if grep -q "^ROUTER_MODE=" "$ENV"; then
  sed -i 's/^ROUTER_MODE=.*/ROUTER_MODE=live/' "$ENV"
else
  printf '\n# Router writes enabled. Verified: no scheduled task writes to a router.\nROUTER_MODE=live\n' >> "$ENV"
fi

grep -n "^ROUTER_MODE=" "$ENV"
grep -n "^INCENTIVES_ENABLED=" "$ENV"

cd /root/GAMETECH-BILLING-SYSTEM
docker compose up -d --force-recreate web celery celery-beat 2>&1 | tail -2
sleep 18
docker exec gametech-web printenv | grep -E 'ROUTER_MODE|INCENTIVES'
docker ps --format '{{.Names}}\t{{.Status}}'