#!/bin/bash
set -e
cd /root/GAMETECH-BILLING-SYSTEM
git pull origin main 2>&1 | tail -1
docker compose up -d --force-recreate web >/dev/null 2>&1
sleep 22
echo "--- django check ---"
docker exec gametech-web python manage.py check 2>&1 | tail -1
docker exec gametech-web python manage.py migrate --check >/dev/null 2>&1 \
  && echo "migrations: current" || echo "migrations: PENDING"
echo
echo "--- verify ---"
docker cp /root/wip/vap.py gametech-web:/app/vap.py 2>/dev/null || true
docker exec -i gametech-web python manage.py shell < /root/wip/vap.py 2>&1 | tail -70