#!/bin/bash
cd /root/GAMETECH-BILLING-SYSTEM
git pull origin main 2>&1 | tail -1
docker compose up -d >/dev/null 2>&1
sleep 30
echo "--- django check ---"
docker exec gametech-web python manage.py check 2>&1 | tail -1
docker exec gametech-web python manage.py migrate --check >/dev/null 2>&1 \
  && echo "migrations: current" || echo "migrations: PENDING"
echo
echo "--- containers ---"
docker ps --format '{{.Names}}  {{.Status}}'
echo
echo "--- 5xx in last 30m ---"
docker logs --since 30m gametech-web 2>&1 | grep -cE '" 5[0-9][0-9] ' || true
echo
echo "--- plan catalogue + state ---"
docker cp /root/wip/fcc.py gametech-web:/app/fcc.py >/dev/null 2>&1
docker exec -i gametech-web python manage.py shell < /root/wip/fcc.py 2>&1 | head -32