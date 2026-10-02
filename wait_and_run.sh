#!/bin/bash
# Wait for the web container to answer, then run a probe script inside it.
# Usage: wait_and_run.sh <script_name_in_app>
set -u
SCRIPT="${1:-perf_probe.py}"

echo "waiting for web..."
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://localhost:8000/login/ 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "ready after $((i*5))s"
    break
  fi
  sleep 5
done

# Make sure the container exists and is running before exec.
docker ps --format '{{.Names}}' | grep -q '^gametech-web$' || {
  echo "web not running, starting"
  cd /root/GAMETECH-BILLING-SYSTEM && docker compose up -d >/dev/null 2>&1
  sleep 30
}

rm -f "/app/${SCRIPT%.py}.out"
docker exec -d gametech-web sh -c "python manage.py shell < /app/$SCRIPT > /app/${SCRIPT%.py}.out 2>&1"
echo "launched $SCRIPT"
