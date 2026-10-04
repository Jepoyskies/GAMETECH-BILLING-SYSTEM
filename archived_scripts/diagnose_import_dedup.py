"""
WHY did a 2,041-row dump import only ~288 customers?

Three candidates, and I must not guess:
  A. the importer deduplicates on a business key (phone / name+address)
  B. the importer aborted partway
  C. the importer silently dropped rows

Measure each one against the source file.
"""
import json
import os
from collections import Counter

from billing.legacy_import.parser import iter_rows
from billing.models import Customer

SRC = "/tmp/scale_2041.sql"

rows = [r for t, r in iter_rows(SRC) if t == "customers"]
print("=" * 78)
print("A. HOW MANY DISTINCT BUSINESS KEYS DOES THE SOURCE REALLY HAVE?")
print("=" * 78)
print(f"  rows in the dump                     : {len(rows)}")

for key in ("username", "phone", "email"):
    vals = [str(r.get(key) or "").strip() for r in rows]
    nonempty = [v for v in vals if v]
    print(f"  distinct {key:9}: {len(set(nonempty)):>5} "
          f"(of {len(nonempty)} non-empty)")

def norm_name_addr(r):
    return ((str(r.get("full_name") or "").strip().lower()),
            (str(r.get("address") or "").strip().lower()))

na = [norm_name_addr(r) for r in rows]
print(f"  distinct (name, address)    : {len(set(na)):>5}")

print()
print("=" * 78)
print("B. HOW MANY ROWS COULD THE IMPORTER POSSIBLY HAVE KEPT?")
print("=" * 78)
distinct_phone = len({str(r.get("phone") or "").strip() for r in rows
                      if str(r.get("phone") or "").strip()})
distinct_email = len({str(r.get("email") or "").strip() for r in rows
                      if str(r.get("email") or "").strip()})
print(f"  if it dedupes on username -> up to {len(rows)}")
print(f"  if it dedupes on email    -> up to {distinct_email}")
print(f"  if it dedupes on phone    -> up to {distinct_phone}")
print(f"  if it dedupes on name+addr-> up to {len(set(na))}")
print()
print(f"  ACTUALLY IN CRM NOW       : {Customer.objects.count()}")

print()
print("=" * 78)
print("C. DID IT ABORT? THE IMPORT REPORT SAYS.")
print("=" * 78)
for path in ("/app/billing/data/last_import_report.json",
             "/app/billing/data/import_report.json"):
    if os.path.exists(path):
        print(f"  found {path}")
        with open(path) as f:
            rep = json.load(f)
        for k, v in rep.items():
            if isinstance(v, list):
                print(f"    {k}: list of {len(v)}")
                for item in v[:6]:
                    print(f"        - {item}")
            else:
                print(f"    {k}: {v}")
        break
else:
    print("  no report file found")

print()
print("=" * 78)
print("D. TOP DUPLICATE KEYS IN THE SOURCE")
print("=" * 78)
for key in ("phone", "email"):
    c = Counter(str(r.get(key) or "").strip() for r in rows)
    c.pop("", None)
    print(f"  most repeated {key}:")
    for v, n in c.most_common(5):
        print(f"    {v!r:44} x{n}")
print()
print("=" * 78)
print("VERDICT INPUT")
print("=" * 78)
crm = Customer.objects.count()
print(f"  dump rows      : {len(rows)}")
print(f"  distinct email : {distinct_email}")
print(f"  distinct phone : {distinct_phone}")
print(f"  in CRM now     : {crm}")
print()
if crm == distinct_phone:
    print("  >> MATCHES distinct phone exactly: the importer deduplicates on phone.")
elif crm == distinct_email:
    print("  >> MATCHES distinct email exactly: the importer deduplicates on email.")
elif crm < len(rows) - 10:
    print("  >> Does not match any single dedup key. Needs a deeper look.")
print("=" * 78)
