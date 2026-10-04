#!/bin/bash
cd /root/GAMETECH-BILLING-SYSTEM
git pull origin main 2>&1 | tail -1
echo "--- django check ---"
docker exec gametech-web python manage.py check 2>&1 | tail -1
docker exec gametech-web python manage.py migrate --check >/dev/null 2>&1 \
  && echo "migrations: current" || echo "migrations: PENDING"
echo
echo "--- containers ---"
docker ps --format '{{.Names}}\t{{.Status}}'
echo
echo "--- 5xx in last 2h ---"
docker logs --since 2h gametech-web 2>&1 | grep -cE '" 5[0-9][0-9] ' || true
echo
echo "--- final plan health ---"
docker exec gametech-web python manage.py shell -c "
from billing.services.plan_health import plan_health, health_summary_line
h = plan_health()
print(health_summary_line())
print('plans mapped to a router profile:', h['plans_with_profile'], '/', h['total_plans'])
" 2>&1 | tail -3
echo
echo "--- backups ---"
ls -la /root/backups/PRE_*.dump 2>/dev/null | tail -3