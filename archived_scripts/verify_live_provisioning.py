"""
ROUTER_MODE=live end-to-end: provision Juan onto MikroTik A through the REAL
Sync Manager push endpoint, then read the router back to prove the secret
actually exists there.

Also proves the approval gate: a Technician must NOT be able to push.
"""
import json
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import Customer
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)


dev = MikrotikDevice.objects.get(device_name="Mikrotik A")
cust = Customer.objects.get(pppoe_username="delacruz_juan_e2e")


def router_secrets():
    api = MikrotikAPI(dev)
    conn = api._get_api()
    return {s.get("name"): s for s in conn.get_resource("/ppp/secret").get() or []}


hdr("0. STATE BEFORE")
before = router_secrets()
print(f"  secrets on {dev.device_name}: {list(before)}")
print(f"  Juan's secret '{cust.pppoe_username}' present? "
      f"{cust.pppoe_username in before}")
print(f"  CRM sync_status: {cust.sync_status}")
print(f"  CRM pppoe_password set: {bool(cust.pppoe_password)}")

hdr("1. APPROVAL GATE - a Technician must NOT be able to push")
tech = Client(); tech.force_login(U.objects.get(username="Merk"))
r = tech.post(f"/devices/devices/{dev.id}/sync/push/",
              {"pppoe_username": cust.pppoe_username}, follow=False)
print(f"  Technician push -> HTTP {r.status_code} {r.headers.get('Location','')}")
check("technician is blocked from pushing to the router",
      r.status_code in (302, 403), f"HTTP {r.status_code}")
mid = router_secrets()
check("technician's attempt created nothing on the router",
      mid.get(cust.pppoe_username, {}).get("name") is None)

hdr("2. STAFF (CSR) PUSHES Juan through the Sync Manager")
csr = Client(); csr.force_login(U.objects.get(username="Vince"))
r = csr.post(f"/devices/devices/{dev.id}/sync/push/",
             {"pppoe_username": cust.pppoe_username}, follow=False)
print(f"  CSR push -> HTTP {r.status_code} {r.headers.get('Location','')}")

cust.refresh_from_db()
print(f"  CRM sync_status now: {cust.sync_status}")
check("push marked the customer Synced", cust.sync_status == "Synced",
      f"sync_status={cust.sync_status}")

hdr("3. READ THE ROUTER BACK")
after = router_secrets()
print(f"  secrets on {dev.device_name}: {list(after)}")
secret = after.get(cust.pppoe_username)
check("Juan's secret NOW EXISTS on MikroTik A", secret is not None,
      f"name={cust.pppoe_username}")
if secret:
    print(f"     profile  : {secret.get('profile')}")
    print(f"     disabled : {secret.get('disabled')}")
    print(f"     comment  : {secret.get('comment')}")
    print(f"     service  : {secret.get('service')}")
    check("secret is enabled", str(secret.get("disabled")).lower() in ("false", "no", "0"),
          f"disabled={secret.get('disabled')}")
    check("profile matches the customer's plan",
          secret.get("profile") == (cust.plan.name if cust.plan else None),
          f"router={secret.get('profile')} plan={cust.plan.name if cust.plan else None}")

hdr("4. SYNC MANAGER NOW SEES HIM AS SYNCED (no longer 'missing')")
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
page = adm.get(f"/devices/devices/{dev.id}/sync/").content.decode()
check("Juan appears on the sync page", cust.pppoe_username in page)
check("he is no longer listed as missing-on-router",
      "missing_on_router" not in page or cust.pppoe_username not in page)

hdr("5. BILLING STATE UNAFFECTED BY THE ROUTER WRITE")
cust.refresh_from_db()
print(f"  status={cust.status} install={cust.installation_status} expires={cust.expires_at}")
check("customer still active", cust.status == "active")
check("due date intact", cust.expires_at is not None, f"expires={cust.expires_at}")

hdr("6. CLEANUP - remove the test secret so the rig is left clean")
api = MikrotikAPI(dev)
ok, msg = api.delete_pppoe_user(cust.pppoe_username)
print(f"  delete_pppoe_user -> {ok} {msg}")
final = router_secrets()
check("test secret removed from the router", cust.pppoe_username not in final,
      f"remaining={list(final)}")
Customer.objects.filter(pk=cust.pk).update(sync_status="Unverified")

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")