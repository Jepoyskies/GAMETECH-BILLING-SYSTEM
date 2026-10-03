import re, io, csv
from collections import defaultdict

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

INSERT_RE = re.compile(r"^INSERT\s+INTO\s+`?([A-Za-z0-9_]+)`?")
COLUMN_LIST_RE = re.compile(r"^\s*\(([^)]*)\)\s*VALUES", re.I)

def load(path):
    rows = defaultdict(list)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            m = INSERT_RE.match(s)
            if not m: continue
            table = m.group(1)
            cm = COLUMN_LIST_RE.match(s[m.end():])
            if not cm: continue
            names = [c.strip().strip("`") for c in cm.group(1).split(",")]
            payload = s[m.end()+cm.end():]
            guard = 0
            while ";" not in payload and guard < 5000:
                nxt = f.readline()
                if not nxt: break
                payload += nxt.rstrip(); guard += 1
            up = payload.upper()
            if "VALUES" in up:
                payload = payload[up.rindex("VALUES")+6:]
            for tup in split_tuples(payload):
                try:
                    vals = next(csv.reader(io.StringIO(tup.strip()), quotechar="'",
                                           escapechar="\\", skipinitialspace=True))
                except Exception:
                    continue
                if len(vals) == len(names):
                    rows[table].append(dict(zip(names, vals)))
    return rows

A = load("gametech (1).sql")

print("=== PAYMENTS TABLE IN EXPORT ===")
pays = A.get("payments", [])
print("rows:", len(pays))
if pays:
    print("columns:", sorted(pays[0].keys()))
    print("sample row:")
    for k, v in sorted(pays[0].items()):
        print("   ", k, "=", repr(v)[:70])

    # Are these the historical ledger? They matter for outstanding_balance.
    custs = A.get("customers", [])
    cnames = set((r.get("username") or "").strip() for r in custs)
    pnames = set((r.get("username") or "").strip() for r in pays if (r.get("username") or "").strip())
    print()
    print("distinct usernames in customers :", len(cnames))
    print("distinct usernames in payments  :", len(pnames))
    print("payment usernames NOT in customers:", len(pnames - cnames))
    print("customers with NO payment history :", len(cnames - pnames))
    print()
    # sample a few payment usernames
    print("sample payment usernames:", sorted(list(pnames))[:8])

print()
print("=== TABLES PRESENT IN EXPORT (full list) ===")
for t, r in sorted(A.items(), key=lambda kv: -len(kv[1])):
    print("  {:<26} {}".format(t, len(r)))