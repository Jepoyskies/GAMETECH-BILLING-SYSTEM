"""
Build a synthetic 2,041-customer legacy dump to test the import at REAL scale.

Why: every import test so far used the 527-row March dump. Tomorrow's export has
2,041 rows -- roughly 4x. The parser has OOM history (the source comments say
repeated string += on a multi-megabyte statement "gets the process OOM-killed"),
and this box has 1.9 GB of RAM shared with Postgres, Redis, Celery and Gunicorn.

The rows are built by re-parsing the real dump and re-emitting it, so the format
the parser sees is byte-for-byte the shape it already handles. Usernames get an
_n suffix so nothing collides with the real subscribers.
"""
from billing.legacy_import.parser import (
    iter_rows, columns_from_create_table,
)

SRC = "/tmp/legacy.sql"
OUT = "/tmp/scale_2041.sql"
TARGET = 2041


def q(v):
    if v is None:
        return "NULL"
    s = str(v).replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"


rows = []
for table, row in iter_rows(SRC):
    if table == "customers":
        rows.append(row)

cols = columns_from_create_table(SRC)["customers"]
print(f"parsed {len(rows)} customer rows from the real dump")
print(f"columns ({len(cols)}): {cols}")

if not rows:
    raise SystemExit("ABORT: no customer rows parsed, cannot build a scale file")

out_rows = []
i = 0
while len(out_rows) < TARGET:
    src = rows[i % len(rows)]
    r = dict(src)
    if i >= len(rows):
        r["username"] = f"{src.get('username')}_n{i}"
        if r.get("email"):
            r["email"] = f"{src['email'].split('@')[0]}_n{i}@example.test"
        if r.get("id"):
            r["id"] = str(900000 + i)
    out_rows.append(r)
    i += 1

out_rows = out_rows[:TARGET]

with open(OUT, "w", encoding="utf-8") as f:
    f.write("-- synthetic scale-test dump, "
            f"{len(out_rows)} customers, built from the real legacy dump\n")
    collist = ",".join(f"`{c}`" for c in cols)
    for start in range(0, len(out_rows), 200):
        chunk = out_rows[start:start + 200]
        f.write(f"INSERT INTO `customers` ({collist}) VALUES\n")
        vals = []
        for r in chunk:
            vals.append("(" + ",".join(q(r.get(c)) for c in cols) + ")")
        f.write(",\n".join(vals) + ";\n")

import os
print(f"\nwrote {OUT}: {len(out_rows)} rows, "
      f"{os.path.getsize(OUT):,} bytes")

# Prove it parses back to the right count before we trust it.
back = sum(1 for t, _ in iter_rows(OUT) if t == "customers")
print(f"re-parsed back: {back} customer rows")
if back != TARGET:
    raise SystemExit(f"ABORT: round-trip gave {back}, expected {TARGET}")
print("round-trip OK")