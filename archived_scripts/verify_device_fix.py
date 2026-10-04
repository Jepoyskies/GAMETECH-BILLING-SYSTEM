"""Did the import put customers on the REAL router this time?"""
from django.db.models import Count
from network_manager.models import MikrotikDevice
from billing.models import Customer

res = []


def check(label, ok, detail=""):
    res.append((bool(ok), label, detail))
    print(f"  [{'PASS' if ok else '**FAIL**'}] {label} {detail}")


print("=" * 76)
print("DEVICES AFTER THE FIX")
print("=" * 76)
for d in MikrotikDevice.objects.annotate(n=Count("customer")).order_by("-n"):
    print(f"  {d.device_name:34} {d.ip_address:16} customers={d.n}")

names = list(MikrotikDevice.objects.values_list("device_name", flat=True))
print()
check("no phantom 'ccr2116.v1' device exists",
      "ccr2116.v1" not in names, f"devices={names}")
check("exactly 4 devices (as registered)", len(names) == 4, f"count={len(names)}")

real = MikrotikDevice.objects.filter(device_name="ccr2116.v1 - patag").first()
check("the real patag router still exists", real is not None)
if real:
    n = Customer.objects.filter(mikrotik_device=real).count()
    print(f"  customers on 'ccr2116.v1 - patag': {n}")
    check("imported customers landed on the REAL router", n > 400, f"n={n}")

orphan = Customer.objects.filter(mikrotik_device__isnull=True).count()
check("no customer left without a router", orphan == 0, f"orphans={orphan}")

print()
print("=" * 76)
print(f"{sum(1 for r in res if r[0])}/{len(res)} passed")
print("=" * 76)
