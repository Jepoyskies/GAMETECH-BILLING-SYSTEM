"""Compile every template in the project and report syntax errors.

Run on the host against a Django settings module, or inside the container.
This catches {%- %}, unclosed blocks and bad filter arguments BEFORE deploy,
instead of discovering them as a 500 in production.
"""
import os
import sys

import django
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gametech_core.settings")
django.setup()

from django.template.loader import get_template  # noqa: E402
from django.template import engines  # noqa: E402

from pathlib import Path  # noqa: E402

root = Path(settings.BASE_DIR) if hasattr(settings, "BASE_DIR") else Path.cwd()
roots = [root / "billing" / "templates", root / "network_manager" / "templates",
         root / "dispatch" / "templates", root / "customer_portal" / "templates"]

files = []
for r in roots:
    if r.exists():
        files += [p for p in r.rglob("*.html")]

bad = []
dj = engines["django"]
for p in sorted(files):
    rel = p.relative_to(root)
    name = str(rel).replace("\\", "/")
    try:
        dj.get_template(name)
    except Exception as e:
        bad.append((name, "%s: %s" % (type(e).__name__, str(e)[:150])))

print("checked %d templates" % len(files))
if bad:
    print("\nBROKEN (%d):" % len(bad))
    for n, e in bad:
        print("  %-70s %s" % (n[:70], e))
    sys.exit(1)
print("ALL TEMPLATES OK")
