import re, io, csv
from collections import defaultdict, Counter

def load(path):
    INSERT_RE = re.compile(r"^INSERT\s+INTO\s+`?([A-Za-z0-9_]+)`?")
    COLUMN_LIST_RE = re.compile(r"^\s*\(([^)]*)\)\s*VALUES", re.I)
    rows = defaultdict(list)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            m = INSERT_RE.match(s)
            if not m:
                continue
            table = m.group(1)
            cm = COLUMN_LIST_RE.match(s[m.end():])
            if not cm:
                continue
            names = [c.strip().strip("`") for c in cm.group(1).split(",")]
            start = m.end() + cm.end()
            payload = s[start:]
            guard = 0
            while ";" not in payload and guard < 5000:
                nxt = f.readline()
                if not nxt:
                    break
                payload += nxt.rstrip(); guard += 1
            body = payload
            up = body.upper()
            if "VALUES" in up:
                body = body[up.rindex("VALUES") + 6:]
            for tup in split_tuples(body):
                try:
                    vals = next(csv.reader(io.StringIO(tup.strip()), quotechar="'",
                                           escapechar="\\", skipinitialspace=True))
                except Exception:
                    continue
                if len(vals) == len(names):
                    rows[table].append(dict(zip(names, vals)))
    return rows

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

A = load("gametech (1).sql")
B = load("backups/backup-2026-03-20_06-21-43.sql")

print("=== gametech (1).sql ===")
for t, r in sorted(A.items(), key=lambda kv: -len(kv[1])):
    print("  {:<22} {}".format(t, len(r)))
print("=== backup-2026-03-20 ===")
for t, r in sorted(B.items(), key=lambda kv: -len(kv[1])):
    print("  {:<22} {}".format(t, len(r)))

def users(tbl):
    return set((r.get("username") or "").strip() for r in tbl if (r.get("username") or "").strip())

ua = users(A.get("customers", []))
ub = users(B.get("customers", []))
print("\n=== USERNAME OVERLAP ===")
print("  gametech (1)      :", len(ua))
print("  backup-2026       :", len(ub))
print("  in BOTH           :", len(ua & ub))
print("  only in gametech  :", len(ua - ub))
print("  only in backup    :", len(ub - ua))
print("  UNION             :", len(ua | ub))
print("  SUM (double-count):", len(ua) + len(ub))

with open("archived_scripts/union_usernames.txt", "w", encoding="utf-8") as f:
    for u in sorted(ua | ub):
        f.write(u + "\n")

# Check the backup's own customer/pppoe counts
print("\n=== backup detail ===")
print("  backup customers  :", len(B.get("customers", [])))
print("  backup pppoe_users:", len(B.get("pppoe_users", [])))
print("  gametech pppoe    :", len(A.get("pppoe_users", [])))

pa = set((r.get("username") or "").strip() for r in A.get("pppoe_users", []) if (r.get("username") or "").strip())
pb = set((r.get("username") or "").strip() for r in B.get("pppoe_users", []) if (r.get("username") or "").strip())
print("  pppoe union       :", len(pa | pb))