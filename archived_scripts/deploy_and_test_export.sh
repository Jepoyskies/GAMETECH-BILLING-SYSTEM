#!/bin/bash
set -e
cd /root/GAMETECH-BILLING-SYSTEM
git pull origin main 2>&1 | tail -1
docker compose up -d --force-recreate web 2>&1 | tail -1
sleep 16
docker exec gametech-web python manage.py check 2>&1 | tail -1
echo
echo "=== CUSTOMER CSV EXPORT TEST ==="
docker exec -i gametech-web python manage.py shell <<'PY'
import csv, io
from django.test import Client
from django.contrib.auth import get_user_model
U = get_user_model()

csr = Client(); csr.force_login(U.objects.get(username="Vince"))
r = csr.get("/customers/export/csv/")
print("CSR GET /customers/export/csv/ ->", r.status_code, len(r.content), "bytes")
print("Content-Disposition:", r.headers.get("Content-Disposition"))
rows = list(csv.DictReader(io.StringIO(r.content.decode())))
print("rows:", len(rows))
if rows:
    print("columns:", list(rows[0].keys()))
    print("sample row:", {k: rows[0][k] for k in list(rows[0])[:8]})
    leaked = [c for c in rows[0] if "password" in c.lower()]
    print("PASSWORD LEAKED IN EXPORT:", bool(leaked), leaked)

r2 = csr.get("/customers/export/csv/?issues=1")
rows2 = list(csv.DictReader(io.StringIO(r2.content.decode())))
print("issues filter rows:", len(rows2))

tech = Client(); tech.force_login(U.objects.get(username="Merk"))
r3 = tech.get("/customers/export/csv/")
print("Technician export ->", r3.status_code, "(must NOT be 200)")
PY