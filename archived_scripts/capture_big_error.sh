#!/bin/bash
# Run the 2,041-row import and capture the FULL log so the traceback is visible.
# The earlier attempt's output was swallowed by a grep; this one keeps everything.
set -e
cd /root/GAMETECH-BILLING-SYSTEM

docker compose up -d >/dev/null 2>&1
sleep 20

docker cp /root/wip/scale_2041.sql gametech-web:/tmp/scale_2041.sql

echo "=== customers before ==="
docker exec gametech-web python manage.py shell -c \
  "from billing.models import Customer; print(Customer.objects.count())" 2>&1 | tail -1

echo
echo "=== running 2,041 import, full log -> /tmp/big.log ==="
docker exec -d gametech-web sh -c \
  "python manage.py import_legacy_customers /tmp/scale_2041.sql > /tmp/big.log 2>&1; echo EXIT=\$? >> /tmp/big.log"

echo "started in background; polling..."
for i in $(seq 1 60); do
  sleep 30
  if docker exec gametech-web sh -c "grep -q EXIT= /tmp/big.log 2>/dev/null"; then
    echo "finished after ~$((i*30))s"
    break
  fi
  N=$(docker exec gametech-web python manage.py shell -c \
    "from billing.models import Customer; print(Customer.objects.count())" 2>/dev/null | tail -1)
  echo "  t+$((i*30))s  customers=$N"
done

echo
echo "=== EXIT CODE ==="
docker exec gametech-web sh -c "grep EXIT= /tmp/big.log" || echo "(still running)"

echo
echo "=== TRACEBACK (if any) ==="
docker exec gametech-web sh -c "grep -n -A30 'Traceback' /tmp/big.log | tail -45" || echo "(none)"

echo
echo "=== LAST 30 LINES ==="
docker exec gametech-web tail -30 /tmp/big.log

echo
echo "=== customers after ==="
docker exec gametech-web python manage.py shell -c \
  "from billing.models import Customer; print(Customer.objects.count())" 2>&1 | tail -1