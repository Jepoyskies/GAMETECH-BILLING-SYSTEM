"""
REDONE PROPERLY: is_test_data=True makes the signal skip entirely, so the
earlier probe did not actually prove staging behaviour.

This runs with a REAL customer record (is_test_data=False) -- exactly what an
import produces -- and verifies against the live router that nothing is
provisioned and nothing is enabled until staff act.
"""
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import Customer, SubscriptionPlan
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


dev = MikrotikDevice.objects.get(device_name="Mikrotik A")
plan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()
uname = "e2e_real_stage"
Customer.objects.filter(pppoe_username=uname).delete()


def router_state():
    api = MikrotikAPI(dev)
    conn = api._get_api()
    return {s.get("name"): str(s.get("disabled")).lower()
            for s in conn.get_resource("/ppp/secret").get() or []}


print("=" * 76)
print("REAL customer record (is_test_data=False) -- what an import produces")
print("=" * 76)
base = router_state()
print(f"  router secrets before: {base}")

c = Customer.objects.create(
    full_name="Real Stage Probe", pppoe_username=uname, pppoe_password="RealProbe123",
    status="active", installation_status="installed", plan=plan,
    mikrotik_device=dev, is_test_data=False)   # <-- NOT test data
c.refresh_from_db()
print(f"  created customer #{c.id}  sync_status = {c.sync_status}")

after = router_state()
print(f"  router secrets after : {after}")

check("no secret was written to the router", uname not in after,
      f"router now has {sorted(after)}")
check("router is byte-identical to before", after == base)
check("customer is STAGED as Pending for staff review",
      c.sync_status == "Pending", f"sync_status={c.sync_status}")

print()
print("=" * 76)
print("A router-relevant EDIT must re-stage it")
print("=" * 76)
c.plan = SubscriptionPlan.objects.exclude(id=plan.id).filter(price__gt=0).first()
c.save()
c.refresh_from_db()
print(f"  after a plan change: sync_status = {c.sync_status}")
check("plan change re-stages the customer", c.sync_status == "Pending",
      f"sync_status={c.sync_status}")

print()
print("=" * 76)
print("A NON-router edit must NOT re-stage (keeps the queue trustworthy)")
print("=" * 76)
c.sync_status = "Synced"; c.save(update_fields=["sync_status"])
c.phone = "09179876543"
c.save()
c.refresh_from_db()
print(f"  after a phone-only change: sync_status = {c.sync_status}")
check("phone-only edit leaves it alone", c.sync_status == "Synced",
      f"sync_status={c.sync_status}")

print()
print("=" * 76)
print("SYNC MANAGER must surface it for approval")
print("=" * 76)
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
page = adm.get(f"/devices/devices/{dev.id}/sync/").content.decode()
check("customer appears on the Sync Manager page", uname in page)
check("the page offers a Push action", "push" in page.lower())
check("nothing on the router changed", router_state() == base)

print()
print("=" * 76)
print("ONLY STAFF PUSH WRITES, and it starts ENABLED only after that")
print("=" * 76)
tech = Client(); tech.force_login(U.objects.get(username="Merk"))
tech.post(f"/devices/devices/{dev.id}/sync/push/", {"pppoe_username": uname})
check("technician push is refused", uname not in router_state(),
      "nothing created by a technician")

csr = Client(); csr.force_login(U.objects.get(username="Vince"))
csr.post(f"/devices/devices/{dev.id}/sync/push/", {"pppoe_username": uname})
st = router_state()
print(f"  after staff push: {uname} -> disabled={st.get(uname)}")
check("staff push created the secret", uname in st)
check("secret is enabled only AFTER staff approval",
      st.get(uname) in ("false", "no", "0"), f"disabled={st.get(uname)}")

print()
print("=" * 76)
print("CLEANUP")
print("=" * 76)
api = MikrotikAPI(dev)
print("  delete ->", api.delete_pppoe_user(uname))
check("rig restored", router_state() == base, f"now={router_state()}")
Customer.objects.filter(pppoe_username=uname).delete()

print()
print("=" * 76)
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
print("=" * 76)