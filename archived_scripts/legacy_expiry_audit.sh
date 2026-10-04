#!/bin/bash
python3 - <<'PY'
import re, collections
F="/root/backups/backup-2026-03-20_06-21-43.sql"
txt=open(F,encoding="utf-8",errors="replace").read()
m=re.search(r"INSERT INTO `customers`.*?;", txt, re.S)
block=m.group(0)
rows=re.findall(r"\(([^()]*)\)", block)
print("customer rows parsed:", len(rows))

zero=0; good=0; nulls=0; samples=[]
for r in rows:
    # expires_at is the 5th column per the schema; grab any 'YYYY-MM-DD HH:MM:SS'
    ds=re.findall(r"'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'", r)
    if not ds:
        nulls+=1
    elif any(d.startswith("0000-00-00") for d in ds):
        zero+=1
    else:
        good+=1
        if len(samples)<6: samples.append(ds[:2])
print(f"  rows with a real expires_at : {good}")
print(f"  rows with ZERO-DATE        : {zero}")
print(f"  rows with no date at all   : {nulls}")
print("  sample dates:", samples)

# connection column values
conn=collections.Counter(re.findall(r",'(Connected|Disconnected|connected|disconnected|online|offline)',", block))
print("\nlegacy customers.connection values:", dict(conn))

# how many distinct plan_name
plans=collections.Counter(re.findall(r",'((?:pppoe|GIMI|GTipid)?[^']*?Mbps[^']*)',", block))
print("\ntop legacy plan_name values:")
for k,v in plans.most_common(12):
    print(f"   {k:28} {v}")
PY