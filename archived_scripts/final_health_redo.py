"""Redo the two sections my script got wrong: Role Editor URL and router fields."""
from django.contrib.auth import get_user_model
from django.test import Client
from network_manager.models import MikrotikDevice

U = get_user_model()
res = []


def check(label, ok, detail=""):
    res.append((bool(ok), label, detail))
    print(f"  [{'PASS' if ok else '**FAIL**'}] {label} {detail}")


adm = Client(); adm.force_login(U.objects.get(username="Jep"))

print("=" * 78)
print("4b. ROLE EDITOR (the source of truth for billing access)")
print("=" * 78)
for url in ("/staff/roles/",):
    r = adm.get(url, follow=True)
    check(f"role editor {url}", r.status_code == 200, f"HTTP {r.status_code}")
    html = r.content.decode()
    check("it renders role content", len(html) > 2000, f"{len(html)} bytes")
    for probe in ("can_access_billing", "Billing", "role"):
        check(f"mentions {probe!r}", probe in html)

print()
print("=" * 78)
print("7b. ROUTERS (correct fields)")
print("=" * 78)
for d in MikrotikDevice.objects.all():
    print(f"  {d.device_name:32} {d.ip_address:16} port={d.api_port} "
          f"health={d.health_status} reason={d.health_reason or '-'}")

print()
print("=" * 78)
print("SUMMARY")
print("=" * 78)
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")
