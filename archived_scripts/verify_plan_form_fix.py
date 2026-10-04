"""Prove the plan form can now actually FIX what the banner complains about."""
from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import SubscriptionPlan
from billing.services.plan_health import plan_health
from network_manager.sync_helpers import desired_profile
from django.utils import timezone

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


hdr = lambda s: print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)

p = SubscriptionPlan.objects.get(name="5Mbps")
print(f"before: router_profile={p.router_profile!r} speed_mbps={p.speed_mbps} "
      f"effective={p.effective_router_profile}")

hdr("1. THE EDIT FORM OFFERS THE FIELD")
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
page = adm.get(f"/plans/edit/{p.id}/").content.decode()
check("edit form has a router_profile input", 'name="router_profile"' in page)
check("edit form has a speed_mbps input", 'name="speed_mbps"' in page)
check("form shows what will be pushed", p.effective_router_profile in page)

hdr("2. THE ADD FORM OFFERS IT TOO")
addpage = adm.get("/plans/add/").content.decode()
check("add form has router_profile", 'name="router_profile"' in addpage)
check("add form has speed_mbps", 'name="speed_mbps"' in addpage)

hdr("3. SETTING IT ACTUALLY CHANGES WHAT THE SYNC PUSHES")
r = adm.post(f"/plans/edit/{p.id}/", {
    "plan_name": "5Mbps", "speed_up": "5 Mbps", "speed_down": "5 Mbps",
    "price": "500.00", "validity_days": "30", "description": "",
    "router_profile": "pppoe-5m_500", "speed_mbps": "5",
})
p.refresh_from_db()
print(f"after : router_profile={p.router_profile!r} speed_mbps={p.speed_mbps} "
      f"effective={p.effective_router_profile}")
check("router_profile saved", p.router_profile == "pppoe-5m_500", f"{p.router_profile!r}")
check("effective_router_profile uses it", p.effective_router_profile == "pppoe-5m_500")
check("the plan is no longer reported as unmapped",
      "5Mbps" not in {u["name"] for u in plan_health()["unmapped"]})

hdr("4. THE HEALTH BANNER REACTS")
h = plan_health()
print(f"  now: {len(h['ambiguous'])} collisions, {len(h['unmapped'])} unmapped")
adm2 = Client(); adm2.force_login(U.objects.get(username="Jep"))
dev = __import__("network_manager.models", fromlist=["MikrotikDevice"]) \
    .MikrotikDevice.objects.get(device_name="Mikrotik A")
page = adm2.get(f"/devices/devices/{dev.id}/sync/").content.decode()
check("banner still renders", "Plan catalogue" in page)

hdr("5. REVERT (keep the catalogue honest, do not invent a profile)")
r = adm.post(f"/plans/edit/{p.id}/", {
    "plan_name": "5Mbps", "speed_up": "5 Mbps", "speed_down": "5 Mbps",
    "price": "500.00", "validity_days": "30", "description": "",
    "router_profile": "", "speed_mbps": "5",
})
p.refresh_from_db()
check("profile cleared again", not p.router_profile, f"{p.router_profile!r}")

print()
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")