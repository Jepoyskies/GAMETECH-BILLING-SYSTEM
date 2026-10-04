"""Use the project's own parser to find out why payments are orphaned."""
from collections import Counter
from billing.legacy_import import iter_rows

F = "/tmp/legacy.sql"

cust = list(iter_rows(F, "customers"))
pay = list(iter_rows(F, "payments"))
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
print("sample:", list(orphans.items())[:15])

ci = {u: n for u, n in orphans.items() if u.lower() not in {c.lower() for c in cu}}
print(f"\norphans that match IGNORING CASE: {len(ci)}")

ws = {u: n for u, n in orphans.items() if u.strip() not in cu}
print(f"orphans that match after strip(): {len(ws)}")

# do the orphan payments carry an amount we should know about?
tot = 0.0
for r in pay:
    u = (r.get("username") or "").strip()
    if u in orphans:
        try:
            tot += float(r.get("amount") or 0)
        except Exception:
            pass
print(f"\nvalue of orphaned payments: PHP {tot:,.2f}")

# Do those usernames exist as customers by a different key (e.g. email/full_name)?
names = {(r.get("full_name") or "").strip().lower() for r in cust}
print(f"\ncustomer full_names present: {len(names)}")