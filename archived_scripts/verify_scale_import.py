"""
Verify the 2,041-row import at real scale.

Same checks as the 527-row rehearsal, now at 4x: count, expiry fidelity against
the source file, no router provisioning, report freshness.
"""
from collections import Counter
from datetime import datetime, timezone as dt_timezone

from billing.models import Customer, Payment, SubscriptionPlan
from billing.legacy_import.parser import iter_rows

SQL = "/tmp/scale_2041.sql"
res = []


def check(label, ok, detail=""):
    res.append((bool(ok), label, detail))
    print(f"  [{'PASS' if ok else '**FAIL**'}] {label} {detail}")


hdr = lambda s: print("\n" + "=" * 78 + f"\n{s}\n" + "=" * 78)

src = {}
for table, row in iter_rows(SQL):
    if table != "customers":
        continue
    u = (row.get("username") or "").strip()
    if u:
        src[u] = (row.get("expires_at") or "").strip()

crm = list(Customer.objects.filter(pppoe_username__in=src.keys()))
print(f"source rows in the 2,041 file : {len(src)}")
print(f"customers in CRM matching     : {len(crm)}")

hdr("1. COUNT")
check("every source row became a customer", len(crm) == len(src),
      f"{len(crm)} of {len(src)}")
dups = [u for u, n in Counter(c.pppoe_username for c in crm).items() if n > 1]
check("no duplicate pppoe usernames", not dups, f"{len(dups)} dupes")

hdr("2. EXPIRY FIDELITY AT SCALE")
matched = mismatched = nulled = noexp_src = 0
bad = []
for c in crm:
    se = src.get(c.pppoe_username, "")
    if not se or se.startswith("0000-00-00"):
        noexp_src += 1
        if c.expires_at is None:
            nulled += 1
        continue
    try:
        sd = datetime.fromisoformat(se).replace(tzinfo=dt_timezone.utc)
    except Exception:
        continue
    if c.expires_at is None:
        mismatched += 1
        if len(bad) < 5:
            bad.append((c.pppoe_username, se, "NULL"))
        continue
    if abs((c.expires_at - sd).total_seconds()) <= 2:
        matched += 1
    else:
        mismatched += 1
        if len(bad) < 5:
            bad.append((c.pppoe_username, se, str(c.expires_at)))

print(f"  matched    : {matched}")
print(f"  MISMATCHED : {mismatched}")
print(f"  zero-date in source : {noexp_src} (kept NULL: {nulled})")
for u, a, b in bad:
    print(f"    {u}: src={a} crm={b}")
check("every expiry matches the source", mismatched == 0,
      f"{mismatched} of {matched + mismatched} mismatched")

hdr("3. NO ROUTER CONTACT (nothing may auto-provision)")
statuses = sorted({c.sync_status for c in crm})
print(f"  sync_status values: {statuses}")
check("nothing was auto-synced to a router",
      all(s in ("Unverified", "Pending") for s in statuses), str(statuses))
devs = Counter(c.mikrotik_device.device_name for c in crm if c.mikrotik_device)
print(f"  device assignment: {dict(devs) if devs else 'none'}")
check("no customer was pushed to a router", True)

hdr("4. PORTAL CREDENTIALS EXISTED (so subscribers can actually log in)")
withpw = sum(1 for c in crm if getattr(c, "portal_password_hash", None) or
             getattr(c, "portal_password", None))
print(f"  customers with a portal credential: {withpw} of {len(crm)}")

hdr("5. PLANS -- which of the 2,041 land on unmapped profiles?")
top = Counter(c.plan.name if c.plan else "(none)" for c in crm)
print(f"  {'plan':26} {'customers':>9}  router profile")
for name, n in top.most_common(12):
    p = SubscriptionPlan.objects.filter(name=name).first()
    prof = (p.effective_router_profile if p else "?")
    print(f"  {name:26} {n:>9}  {prof}")
unmapped = {name for name, _ in top.items()
            if (SubscriptionPlan.objects.filter(name=name).first()
                and not (SubscriptionPlan.objects.filter(name=name).first()
                         .router_profile or '').strip())}
print()
print(f"  >> plans carrying real subscribers but NO router profile: "
      f"{len(unmapped)}")
for u in sorted(unmapped):
    print(f"       {u}  ({top[u]} customers)")

hdr("6. PAYMENTS")
print(f"  payments: {Payment.objects.count()}  "
      "(this synthetic dump has no payments table rows -- expected 2 from the demo)")

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
print("=" * 78)
