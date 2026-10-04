"""
Audit for the same class of hole as customer_list: views that expose customer /
billing / money data but carry NO role gate beyond @login_required.

Static scan of the decorators immediately above each view def, then a live probe
of the suspicious ones.
"""
import ast
import pathlib

ROOT = pathlib.Path("/app")
STDLIB_OK = set()

INTERESTING = ("customer", "payment", "rebate", "invoice", "billing", "payout",
               "commission", "agent", "prospect", "cignal", "plan", "subscription")

rows = []
for py in ROOT.rglob("*.py"):
    if any(p in str(py) for p in ("/tests/", "/test_", "migrations", "/venv/", "/node_modules")):
        continue
    try:
        tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name.lower()
        if not any(k in name for k in INTERESTING):
            continue
        if name.startswith(("api_", "_")):
            continue
        decs = []
        for d in node.decorator_list:
            try:
                decs.append(ast.unparse(d))
            except Exception:
                decs.append("?")
        joined = " ".join(decs).lower()
        has_role = any(k in joined for k in ("role_required", "module_required",
                                             "permission_required", "user_passes_test",
                                             "dispatch_permission_required",
                                             "action_required", "staff_member_required"))
        has_login = "login_required" in joined
        rows.append({
            "view": f"{py.relative_to(ROOT)}:{node.lineno} {node.name}",
            "login": has_login,
            "role": has_role,
            "decs": "; ".join(decs)[:110],
        })

unguarded = [r for r in rows if r["login"] and not r["role"]]
print("=" * 78)
print(f"VIEWS TOUCHING CUSTOMER/BILLING DATA: {len(rows)}")
print(f"  with a role gate : {len([r for r in rows if r['role']])}")
print(f"  NO role gate     : {len(unguarded)}")
print("=" * 78)
for r in unguarded:
    print(f"  {r['view']}")
    print(f"      decorators: {r['decs']}")

print()
print("=" * 78)
print("DECORATED-BUT-NO-LOGIN (worth a look)")
print("=" * 78)
for r in rows:
    if not r["login"]:
        print(f"  {r['view']}\n      {r['decs']}")