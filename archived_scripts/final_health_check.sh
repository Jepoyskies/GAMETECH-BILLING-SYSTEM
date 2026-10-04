#!/bin/bash
set -e
cd /root/GAMETECH-BILLING-SYSTEM
git pull origin main 2>&1 | tail -1
docker exec gametech-web python manage.py check 2>&1 | tail -1
docker exec gametech-web python manage.py migrate --check 2>&1 | tail -1 && echo "migrations: up to date"
echo
echo "=== containers ==="
docker ps --format '{{.Names}}\t{{.Status}}'
echo
echo "=== live HTTP ==="
for u in /login/ / /customers/ /cignal-dashboard/ /dispatch/queue/ /portal/dashboard/; do
  printf "  %-22s %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000$u)"
done
echo
echo "=== recent 5xx in web log ==="
docker logs --since 30m gametech-web 2>&1 | grep -cE '" 5[0-9][0-9] ' || echo 0