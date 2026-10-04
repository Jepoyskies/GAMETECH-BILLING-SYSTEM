#!/bin/bash
set -e
cd /root/GAMETECH-BILLING-SYSTEM
git pull origin main 2>&1 | tail -1
docker compose up -d --force-recreate web 2>&1 | tail -1
sleep 18
docker exec gametech-web python manage.py check 2>&1 | tail -1
docker exec gametech-web python manage.py migrate --check 2>&1 | tail -1 && echo "migrations current"
docker cp /root/wip/phui.py gametech-web:/app/phui.py 2>/dev/null || true
docker exec -i gametech-web python manage.py shell < /root/wip/phui.py 2>&1 | tail -45