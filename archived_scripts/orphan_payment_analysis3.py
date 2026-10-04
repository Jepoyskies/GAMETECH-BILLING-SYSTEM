"""Use the project's own parser to find out why payments are orphaned."""
from collections import Counter
from billing.legacy_import.parser import iter_rows

F = "/tmp/legacy.sql"

by_table = {}
for table, row in iter_rows(F):
    by_table.setdefault(table, []).append(row)

cust = by_table.get("customers", [])
pay = by_table.get("payments", [])
print(f"customers rows: {len(cust)}")
print(f"payments rows : {len(pay)}")

cu = Counter()
for r in cust:
    u = (r.get("username") or "").strip()
    if u:
        cu[u] += 1
print(f"distinct customer usernames: {len(cu)}")

payu = Counter()
for r in pay:
    u = (r.get("username") or "").strip()
    if u:
        payu[u] += 1
print(f"distinct payment usernames : {len(payu)}")

orphans = {u: n for u, n in payu.items() if u not in cu}
print(f"\nORPHAN payment usernames: {len(orphans)}  ({sum(orphans.values())} rows)")
print("sample:", list(orphans.items())[:12])

lower = {c.lower() for c in cu}
ci = {u: n for u, n in orphans.items() if u.lower() in lower}
print(f"\norphans matching if we IGNORE CASE: {len(ci)}")

tot = 0.0
for r in pay:
    u = (r.get("username") or "").strip()
    if u in orphans:
        try:
            tot += float(r.get("amount") or 0)
        except Exception:
            pass
print(f"value of orphaned payments: PHP {tot:,.2f}")

# Are orphan usernames present as customers under a different column?
allcust_vals = set()
for r in cust:
    for k in ("username", "full_name", "email"):
        v = (r.get(k) or "").strip().lower()
        if v:
            allcust_vals.add(v)
recoverable = [u for u in orphans if u.lower() in allcust_vals]
print(f"orphans recoverable via any customer column: {len(recoverable)}")