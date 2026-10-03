"""
Router <-> CRM reconciliation audit.

READ-ONLY. Never writes to a router. Buckets every CRM customer into an
operational category so the owner can see who is who, and cross-checks the
PPPoE secrets that actually exist on the routers against the CRM.

Categories mirror the triage language used in dispatch:
  A. ACTIVE + CONNECTED + has expiry   -> healthy
  B. ACTIVE + CONNECTED + NO expiry   -> revenue risk (free ride)
  C. ACTIVE but OFFLINE               -> outage, dispatch a technician
  D. EXPIRED but CONNECTED            -> unpaid but still online
  E. PENDING install, no ticket       -> stranded, nobody dispatched
  F. Not on any router                -> secret missing, needs provisioning
"""

from billing.models import Customer
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

print("=" * 78)
print("ROUTER <-> CRM RECONCILIATION AUDIT  (read-only)")
print("=" * 78)

# ---------------------------------------------------- pull live PPPoE secrets
router_users = {}          # pppoe_username -> {router, disabled, profile}
router_errors = []

for dev in MikrotikDevice.objects.all():
    try:
        api = MikrotikAPI(dev)
        conn = api._get_api()
        secrets = conn.get_resource("/ppp/secret").get()   # READ ONLY
        n = 0
        for s in secrets or []:
            name = s.get("name")
            if not name:
                continue
            router_users[name] = {
                "router": dev.device_name,
                "disabled": str(s.get("disabled", "no")).lower() in ("true", "yes", "1"),
                "profile": s.get("profile", ""),
                "has_password": bool(s.get("password")),
            }
            n += 1
        print(f"  {dev.device_name:28} reachable, {n} PPPoE secrets")
    except Exception as e:
        router_errors.append((dev.device_name, f"{type(e).__name__}: {str(e)[:70]}"))
        print(f"  {dev.device_name:28} UNREACHABLE -> {type(e).__name__}: {str(e)[:70]}")

if router_errors:
    print("\n  !! Some routers could not be read. Buckets below treat those")
    print("     routers as EMPTY, which will look like 'customer offline'.")
    print("     Do not act on buckets until these are reachable.")

print(f"\n  total secrets seen on routers: {len(router_users)}")

# ------------------------------------------------------------- bucket the CRM
buckets = {k: [] for k in "ABCDEF"}
for c in Customer.objects.select_related("mikrotik_device"):
    name = c.pppoe_username
    on_router = name in router_users
    info = router_users.get(name, {})
    connected = on_router and not info.get("disabled", True)
    if c.installation_status == "pending":
        buckets["E"].append(c)
    elif not on_router:
        buckets["F"].append(c)
    elif connected and not c.expires_at:
        buckets["B"].append(c)
    elif connected and c.expires_at and c.expires_at.date().isoformat() < __import__("datetime").date.today().isoformat():
        buckets["D"].append(c)
    elif connected and c.status == "active":
        buckets["A"].append(c)
    else:
        buckets["C"].append(c)

LABELS = {
    "A": "ACTIVE + connected + has expiry  (healthy)",
    "B": "ACTIVE + connected + NO expiry   (revenue risk)",
    "C": "ACTIVE but OFFLINE              (outage - dispatch)",
    "D": "EXPIRED but still connected      (unpaid online)",
    "E": "PENDING install                  (needs dispatch)",
    "F": "No secret on any router          (needs provisioning)",
}

print("\n" + "=" * 78)
print("CRM BUCKETS")
print("=" * 78)
for k in "ABCDEF":
    print(f"  [{k}] {LABELS[k]:48} {len(buckets[k])}")
    for c in buckets[k][:8]:
        print(f"        #{c.id:<6} {c.full_name[:28]:30} {c.pppoe_username}")
    if len(buckets[k]) > 8:
        print(f"        ... and {len(buckets[k]) - 8} more")

# ---------------------------------------------- router secrets with no CRM row
orphans = [n for n in router_users if not Customer.objects.filter(pppoe_username=n).exists()]
print("\n" + "=" * 78)
print(f"ORPHAN SECRETS (live on a router, no CRM customer): {len(orphans)}")
for n in orphans[:20]:
    print(f"        {n:32} on {router_users[n]['router']} disabled={router_users[n]['disabled']}")
if len(orphans) > 20:
    print(f"        ... and {len(orphans) - 20} more")

# ------------------------------------------------------ secrets missing a password
nopass = [n for n, i in router_users.items() if not i.get("has_password")]
print(f"\nSECRETS WITH NO PASSWORD SET: {len(nopass)}")
for n in nopass[:15]:
    print(f"        {n}")

if router_errors:
    print("\nROUTERS THAT COULD NOT BE READ:")
    for name, err in router_errors:
        print(f"        {name}: {err}")