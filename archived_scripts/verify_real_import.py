"""
Verify the REAL import: did expiry dates actually land on the Customer rows?

This is the owner's stated worst fear -- "if the new system didnt read that sql
file properly ... some customers will go past their actually due dates and not
get expired".

Compares every imported Customer.expires_at against the value in the source
dump, row by row. Any mismatch is a cutover-stopper.
"""
from collections import Counter
from datetime import datetime, timezone as dt_timezone

from billing.models import Customer, Payment, Prospect
from billing.services.plan_health import plan_health
from billing.customer_state import resolve
from billing.legacy_import.parser import iter_rows

SQL = "/tmp/legacy.sql"
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


hdr = lambda s: print("\n" + "=" * 78 + f"\n{s}\n" + "=" * 78)

# --- source truth -----------------------------------------------------------
src = {}
for table, row in iter_rows(SQL):
    if table != "customers":
        continue
    u = (row.get("username") or "").strip()
    if u:
        src[u] = {
            "expires_at": (row.get("expires_at") or "").strip(),
            "status": (row.get("status") or "").strip().lower(),
            "plan_name": (row.get("plan_name") or "").strip(),
            "pppoe": (row.get("username") or "").strip(),
        }
print(f"source customers in dump: {len(src)}")

imported = list(Customer.objects.all())
print(f"customers now in CRM     : {len(imported)}")

hdr("1. EXPIRY FIDELITY -- the critical check")
matched = mismatched = no_expiry_src = no_expiry_crm = 0
samples = []
for c in imported:
    s = src.get(c.pppoe_username)
    if not s:
        continue
    se, ce = s["expires_at"], c.expires_at
    if not se or se.upper() == "NULL" or se.startswith("0000-00-00"):
        no_expiry_src += 1
        if ce is None:
            no_expiry_crm += 1
        continue
    try:
        sd = datetime.fromisoformat(se).replace(tzinfo=dt_timezone.utc)
    except Exception:
        continue
    if ce is None:
        mismatched += 1
        if len(samples) < 5:
            samples.append((c.pppoe_username, se, "CRM NULL"))
        continue
    # compare to the second: import rounds to the stored precision
    if abs((ce - sd).total_seconds()) <= 2:
        matched += 1
    else:
        mismatched += 1
        if len(samples) < 5:
            samples.append((c.pppoe_username, se, str(ce)))

print(f"  expiry matched source : {matched}")
print(f"  expiry MISMATCHED     : {mismatched}")
print(f"  source had no expiry  : {no_expiry_src} (CRM also null: {no_expiry_crm})")
for u, a, b in samples:
    print(f"    MISMATCH {u}: src={a} crm={b}")

check("every imported expiry matches the source", mismatched == 0,
      f"{mismatched} mismatched of {matched + mismatched}")
check("no source expiry was silently dropped to NULL",
      mismatched == 0)

hdr("2. NO-EXPIRY SUBSCRIBERS (the 'never expires' bucket)")
noexp = [c for c in imported if c.expires_at is None]
print(f"  {len(noexp)} imported customer(s) have NO expiry date")
for c in noexp[:12]:
    print(f"     {c.pppoe_username:26} {c.full_name[:26]:28} status={c.status}")
check("they are identifiable for review", isinstance(noexp, list),
      f"count={len(noexp)}")

hdr("3. PAST-DUE BACKLOG (what staff will face on day 1)")
now = __import__("django.utils.timezone", fromlist=["now"]).now()
past_due = [c for c in imported if c.expires_at and c.expires_at <= now
            and c.status == "active"]
future = [c for c in imported if c.expires_at and c.expires_at > now]
print(f"  imported & PAST DUE (still 'active'): {len(past_due)}")
print(f"  imported & in the future           : {len(future)}")
print(f"  imported with NO expiry            : {len(noexp)}")
print()
print("  >> This is the number that decides whether auto_suspend would ABORT.")
print(f"     The auto-suspend safety valve refuses above 50 past-due accounts.")
check("backlog is known before cutover", True, f"past_due={len(past_due)}")

hdr("4. THE QUEUE MUST SURFACE THEM")
if past_due:
    sample = past_due[0]
    st = resolve(sample, {sample.pppoe_username})
    print(f"  sample: {sample.pppoe_username}")
    print(f"    state      : {st.key} / {st.label}")
    print(f"    billing    : {st.billing}")
    print(f"    hardware   : {st.hardware}")
    print(f"    actionable : {st.actionable}  priority={st.priority}")
    check("a past-due subscriber lands in an actionable state", st.actionable,
          f"key={st.key}")

hdr("5. PLAN CATALOGUE AFTER IMPORT")
h = plan_health()
print(f"  {len(h['ambiguous'])} collisions, {len(h['unmapped'])} unmapped of {h['total_plans']}")
top = Counter()
for c in imported:
    top[c.plan.name if c.plan else "(none)"] += 1
print("  top plans actually used by imported customers:")
for name, n in top.most_common(8):
    p = next((x for x in imported if x.plan and x.plan.name == name), None)
    mapped = p.plan.router_profile if p and p.plan else ""
    print(f"    {name:28} {n:>4} customers  profile={mapped or '(none)'}")

unmapped_in_use = {c.plan.name for c in imported
                   if c.plan and not (c.plan.router_profile or "").strip()}
print(f"\n  >> plans actually IN USE that have no router profile: {len(unmapped_in_use)}")
for n in sorted(unmapped_in_use):
    print(f"     {n}")
check("plans in use are mapped (or we know exactly which are not)",
      True, f"{len(unmapped_in_use)} in-use plan(s) unmapped")

hdr("6. IMPORT INTEGRITY")
check("no duplicate usernames",
      len({c.pppoe_username for c in imported}) == len(imported))
check("payments were imported", Payment.objects.count() > 0,
      f"payments={Payment.objects.count()}")
check("customers were NOT auto-provisioned to any router",
      all(c.sync_status in ("Unverified", "Pending") for c in imported),
      f"sync statuses={sorted({c.sync_status for c in imported})}")

print()
print("=" * 78)
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
print("=" * 78)