#!/bin/bash
set -e
cd /root/GAMETECH-BILLING-SYSTEM
git pull origin main 2>&1 | tail -1

echo "=== generate + apply migration for the new plan fields ==="
docker exec gametech-web python manage.py makemigrations billing --name plan_router_profile 2>&1 | tail -5
docker exec gametech-web python manage.py migrate 2>&1 | tail -4

echo
echo "=== backfill from the legacy naming ==="
docker cp /root/wip/backfill.py gametech-web:/app/backfill_plans.py 2>/dev/null || true
docker exec -i gametech-web python manage.py shell < /root/wip/backfill.py 2>&1 | tail -45