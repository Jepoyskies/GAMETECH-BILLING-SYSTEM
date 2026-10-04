#!/bin/bash
# How many legacy customers carry a status the new system has no label for?
F=/root/backups/backup-2026-03-20_06-21-43.sql

echo "=== legacy status values + counts ==="
grep -oE ",'[a-z_]+','" "$F" | head -0   # noop
python3 - <<'PY'
import re, collections
F="/root/backups/backup-2026-03-20_06-21-43.sql"
txt=open(F,encoding="utf-8",errors="replace").read()

# isolate the customers INSERT
m=re.search(r"INSERT INTO `customers`.*?;", txt, re.S)
if not m:
    print("no customers INSERT found"); raise SystemExit
block=m.group(0)

# count status tokens: they appear as ,'status', inside the value tuples
c=collections.Counter(re.findall(r",'((?:active|inactive|suspended|pending|pull out|expired|past_due))',", block))
print("legacy customers.status counts:")
for k,v in c.most_common():
    print(f"   {k:12} {v}")

valid={"active","expired","inactive","pending","suspended","pull out","closed_not_installed"}
unknown={k:v for k,v in c.items() if k not in valid}
print()
print("NOT a valid Customer.STATUS_CHOICES value:")
for k,v in unknown.items():
    print(f"   {k:12} {v}")
PY