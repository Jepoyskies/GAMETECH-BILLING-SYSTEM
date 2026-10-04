#!/bin/bash
docker exec gametech-web python - <<'PY'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gametech_core.settings")
django.setup()
from django.conf import settings
print("INCENTIVES_ENABLED =", getattr(settings, "INCENTIVES_ENABLED", "MISSING"))
PY
docker ps --format '{{.Names}}\t{{.Status}}'