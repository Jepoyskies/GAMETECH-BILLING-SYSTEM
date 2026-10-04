#!/bin/bash
echo "=== INCENTIVES_ENABLED in settings ==="
grep -rn "INCENTIVES_ENABLED" /root/GAMETECH-BILLING-SYSTEM/gametech_core/settings.py || echo "  (not set in settings.py -> defaults to False)"

echo
echo "=== in .env ==="
grep -n "INCENTIVE" /root/GAMETECH-BILLING-SYSTEM/.env || echo "  (not in .env)"

echo
echo "=== effective value in the running container ==="
docker exec gametech-web python - <<'PY'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gametech_core.settings")
django.setup()
from django.conf import settings
print("  INCENTIVES_ENABLED =", getattr(settings, "INCENTIVES_ENABLED", "<<MISSING>>"))
PY