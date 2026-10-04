"""Remove the scale-test rows and the phantom device created before the fix."""
from django.db.models import Count
from network_manager.models import MikrotikDevice
from billing.models import Customer

print("BEFORE:")
for d in MikrotikDevice.objects.annotate(n=Count("customer")):
    print(f"  {d.device_name:34} {d.ip_address:16} customers={d.n}")

# Delete every imported customer, keep only the demo account.
stray = Customer.objects.exclude(pppoe_username="delacruz_juan_e2e")
n, _ = stray.delete()
print(f"\ndeleted {n} imported customer rows")

# The phantom is the device that duplicates a real device's IP.
real_ips = set()
for d in MikrotikDevice.objects.exclude(device_name="ccr2116.v1"):
    if d.ip_address and d.ip_address != "0.0.0.0":
        real_ips.add(d.ip_address)

phantom = MikrotikDevice.objects.filter(device_name="ccr2116.v1").first()
if phantom and phantom.ip_address in real_ips:
    n2, _ = MikrotikDevice.objects.filter(pk=phantom.pk).delete()
    print(f"deleted phantom device 'ccr2116.v1' ({n2} rows) -- its IP "
          f"{phantom.ip_address} belongs to a real registered router")
else:
    print("no phantom device present")

print("\nAFTER:")
for d in MikrotikDevice.objects.annotate(n=Count("customer")):
    print(f"  {d.device_name:34} {d.ip_address:16} customers={d.n}")
print(f"\ncustomers remaining: {Customer.objects.count()}")
