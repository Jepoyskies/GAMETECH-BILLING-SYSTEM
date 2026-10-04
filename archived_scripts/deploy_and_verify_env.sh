#!/bin/bash
set -e
cd /root/GAMETECH-BILLING-SYSTEM
git pull origin main 2>&1 | tail -1
# compose must be re-created, not just restarted, for env changes to land
docker compose up -d --force-recreate web celery celery-beat 2>&1 | tail -2
sleep 18
docker ps --format '{{.Names}}\t{{.Status}}'
echo
docker exec gametech-web python - <<'PY'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gametech_core.settings")
django.setup()
from django.conf import settings
print("INCENTIVES_ENABLED =", getattr(settings, "INCENTIVES_ENABLED", "MISSING"))
print("ROUTER_MODE        =", getattr(settings, "ROUTER_MODE", "MISSING"))
print("SESSION_COOKIE_AGE =", getattr(settings, "SESSION_COOKIE_AGE", "MISSING"))
PY