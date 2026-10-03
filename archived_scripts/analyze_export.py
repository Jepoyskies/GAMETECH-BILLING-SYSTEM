import re, sys, io
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

path = "gametech (1).sql"

INSERT_RE = re.compile(r"^INSERT\s+INTO\s+`?([A-Za-z0-9_]+)`?")
COLUMN_LIST_RE = re.compile(r"^\s*\(([^)]*)\)\s*VALUES", re.I)

def split_tuples(payload):
    out, buf = [], []
    depth = 0; in_str = False; i = 0; n = len(payload)
    while i < n:
        ch = payload[i]
        if in_str:
            if ch == "\\" and i + 1 < n:
                buf.append(ch); buf.append(payload[i+1]); i += 2; continue
            if ch == "'":
                if i + 1 < n and payload[i+1] == "'":
                    buf.append("''"); i += 2; continue
                in_str = False
            buf.append(ch); i += 1; continue
        if ch == "'":
            in_str = True; buf.append(ch); i += 1; continue
        if ch == "(":
            depth += 1
            if depth == 1:
                buf = []; i += 1; continue
        elif ch == ")":
            depth -= 1
            if depth == 0:
                out.append("".join(buf)); buf = []; i += 1; continue
        if depth >= 1:
            buf.append(ch)
        i += 1
    return out

import csv

rows_by_table = defaultdict(list)
with open(path, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        s = line.strip()
        m = INSERT_RE.match(s)
        if not m:
            continue
        table = m.group(1)
        cm = COLUMN_LIST_RE.match(s[m.end():])
        if cm:
            names = [c.strip().strip("`") for c in cm.group(1).split(",")]
            start = m.end() + cm.end()
        else:
            continue
        payload = s[start:]
        while ";" not in payload.split("VALUES", 1)[-1] if "VALUES" in payload else True:
            nxt = f.readline()
            if not nxt:
                break
            payload += nxt.rstrip()
        body = payload
        if "VALUES" in body.upper():
            body = body[body.upper().rindex("VALUES") + 6:]
        for tup in split_tuples(body):
            try:
                vals = next(csv.reader(io.StringIO(tup.strip()), quotechar="'",
                                       escapechar="\\", skipinitialspace=True))
            except Exception:
                continue
            if len(vals) != len(names):
                continue
            rows_by_table[table].append(dict(zip(names, vals)))

print("=== TABLES IN EXPORT ===")
for t, rows in sorted(rows_by_table.items(), key=lambda kv: -len(kv[1])):
    print("  {:<22} {:>7} rows".format(t, len(rows)))

cust = rows_by_table.get("customers", [])
print("\n=== CUSTOMER COLUMNS ===")
if cust:
    print(" ", sorted(cust[0].keys()))

def parse_dt(v):
    if not v or v.upper() == "NULL" or v.startswith("0000-00-00"):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None

now = datetime.utcnow()
past = future = nulls = unparsed = 0
status_counts = Counter()
past_by_status = Counter()
for r in cust:
    st = (r.get("status") or "active").lower()
    status_counts[st] += 1
    d = parse_dt(r.get("expires_at"))
    if d is None:
        if (r.get("expires_at") or "").strip() == "" or (r.get("expires_at") or "NULL").upper() == "NULL" or (r.get("expires_at") or "").startswith("0000-00-00"):
            nulls += 1
        else:
            unparsed += 1
    elif d < now:
        past += 1
        past_by_status[st] += 1
    else:
        future += 1

print("\n=== EXPORT expires_at vs NOW (UTC {}) ===".format(now.strftime("%Y-%m-%d %H:%M")))
print("  PAST DUE   : {}".format(past))
print("  FUTURE     : {}".format(future))
print("  NULL/ZERO  : {}".format(nulls))
print("  UNPARSED   : {}".format(unparsed))
print("\n=== EXPORT status counts ===")
for s, c in status_counts.most_common():
    print("  {:<20} {}".format(s, c))
print("\n=== PAST-DUE broken down by export status ===")
for s, c in past_by_status.most_common():
    print("  {:<20} {}".format(s, c))

pppoe = rows_by_table.get("pppoe_users", [])
print("\n=== PPPoE users in export: {} ===".format(len(pppoe)))

users_with_pp = sum(1 for r in cust if (r.get("username") or "").strip())
print("=== customers with a username: {} ===".format(users_with_pp))

# Save usernames for cross-check against production
unames = [(r.get("username") or "").strip() for r in cust if (r.get("username") or "").strip()]
with open("archived_scripts/export_usernames.txt", "w", encoding="utf-8") as out:
    for u in unames:
        out.write(u + "\n")
print("Wrote {} usernames to archived_scripts/export_usernames.txt".format(len(unames)))