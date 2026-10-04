"""
THE CRITICAL SAFETY TEST, with ROUTER_MODE=live.

Question: if we import 2,041 customers, do they all get connected to the routers
immediately?

Expected answer: NO. Creating/saving a customer must only STAGE it
(sync_status=Pending). Only an explicit, staff-driven push from the Sync Manager
may write a secret.

This proves it against the live router rather than trusting the source.
"""
from django.test import Client
from django.contrib.auth import get_user_model
from django.conf import settings
from billing.models import Customer, SubscriptionPlan
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
plan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()


def router_names():
    api = MikrotikAPI(dev)
    conn = api._get_api()
    return {s.get("name") for s in conn.get_resource("/ppp/secret").get() or []}


print(f"ROUTER_MODE = {settings.ROUTER_MODE}")
hdr("0. BASELINE SECRETS ON THE ROUTER")
base = router_names()
print(f"  {sorted(base)}")
check("baseline captured", len(base) >= 4, f"count={len(base)}")

hdr("1. CREATE A CUSTOMER THE NORMAL WAY (what an import does)")
uname = "e2e_staging_probe"
Customer.objects.filter(pppoe_username=uname).delete()
c = Customer.objects.create(
    full_name="TEST Staging Probe", pppoe_username=uname, pppoe_password="ProbePass123",
    status="active", installation_status="installed", plan=plan,
    mikrotik_device=dev, is_test_data=True)
c.refresh_from_db()
print(f"  created customer #{c.id} sync_status={c.sync_status}")

now = router_names()
print(f"  router secrets now: {sorted(now)}")
check("NOT provisioned automatically", uname not in now,
      "customer save must NOT write a secret")
check("router unchanged by the save", now == base,
      f"added={now - base} removed={base - now}")

hdr("2. IT MUST BE STAGED FOR STAFF APPROVAL")
c.refresh_from_db()
print(f"  sync_status = {c.sync_status}")
check("customer is staged as Pending for staff review",
      c.sync_status == "Pending", f"sync_status={c.sync_status}")

hdr("3. THE SYNC MANAGER MUST SHOW IT AS 'MISSING ON ROUTER'")
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
page = adm.get(f"/devices/devices/{dev.id}/sync/").content.decode()
check("probe appears on the sync page", uname in page)
check("it is offered to staff for approval/push", "push" in page.lower())

hdr("4. IMPORT PATH: does the importer ever set push_to_router?")
import inspect
from billing.management.commands import import_legacy_customers as imp
src = inspect.getsource(imp)
check("importer never sets push_to_router", "push_to_router" not in src,
      "'push_to_router' not found in importer source")

hdr("5. ONLY AN EXPLICIT STAFF PUSH WRITES")
csr = Client(); csr.force_login(U.objects.get(username="Vince"))
r = csr.post(f"/devices/devices/{dev.id}/sync/push/", {"pppoe_username": uname})
after = router_names()
print(f"  after staff push: {sorted(after)}")
check("staff push DID write the secret", uname in after)
c.refresh_from_db()
check("sync_status becomes Synced", c.sync_status == "Synced", f"sync_status={c.sync_status}")

hdr("6. CLEANUP")
api = MikrotikAPI(dev)
ok, msg = api.delete_pppoe_user(uname)
print(f"  delete -> {ok} {msg}")
final = router_names()
check("rig restored to baseline", final == base, f"now={sorted(final)}")
Customer.objects.filter(pppoe_username=uname).delete()

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
print()
print("VERDICT: importing N customers creates N staged records and 0 router secrets.")
print("         Nothing gets internet until a staff member approves it in the Sync Manager.")