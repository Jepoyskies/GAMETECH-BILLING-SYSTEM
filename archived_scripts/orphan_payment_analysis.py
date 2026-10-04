"""Why are 436 of 799 payments orphaned? Compare payment usernames to customer usernames."""
import re, collections, sys

F = "/tmp/legacy.sql"
txt = open(F, encoding="utf-8", errors="replace").read()


def rows(table):
    m = re.search(rf"INSERT INTO `{table}`.*?;", txt, re.S)
    if not m:
        return []
    return re.findall(r"\(([^()]*)\)", m.group(0))


cust_rows = rows("customers")
pay_rows = rows("payments")

# customers columns: id,username,account_type,plan_name,expires_at,...
cust_users = set()
for r in cust_rows:
    parts = [p.strip().strip("'") for p in r.split(",")]
    if len(parts) > 1:
        cust_users.add(parts[1].strip())
        cust_users.add(parts[1].strip().lower())

pay_users = collections.Counter()
for r in pay_rows:
    parts = [p.strip().strip("'") for p in r.split(",")]
    if parts:
        pay_users[parts[0].strip()] += 1

print(f"customers rows      : {len(cust_rows)}")
print(f"distinct cust users : {len(cust_users)}")
print(f"payment rows        : {len(pay_rows)}")
print(f"distinct pay users  : {len(pay_users)}")

orphans = {u: n for u, n in pay_users.items() if u not in cust_users}
print(f"\nORPHAN payment users: {len(orphans)}")
tot = sum(orphans.values())
print(f"orphan payment rows : {tot}")

# case-insensitive retry
orphans_ci = {u: n for u, n in orphans.items() if u.lower() not in cust_users}
print(f"orphans that match if we ignore CASE: {len(orphans_ci)}  <-- casing bug?")
for u, n in list(orphans_ci.items())[:10]:
    print(f"    {u} ({n} payments)")

print("\nsample genuinely-missing usernames:")
for u, n in list(orphans.items())[:15]:
    print(f"    {u:32} {n} payment(s)")

# Do orphan usernames look like they were deleted customers?
print("\nchecking pppoe_users table for the orphans...")
pu = set()
for r in rows("pppoe_users"):
    parts = [p.strip().strip("'") for p in r.split(",")]
    if parts:
        pu.add(parts[0].strip())
hit = [u for u in orphans if u in pu]
print(f"    orphan usernames that DO exist in pppoe_users: {len(hit)} / {len(orphans)}")