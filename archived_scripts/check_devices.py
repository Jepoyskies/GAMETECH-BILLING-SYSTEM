from django.db.models import Count
from network_manager.models import MikrotikDevice

print("DEVICES (name -> how many imported customers point at it)")
print("=" * 78)
for d in MikrotikDevice.objects.annotate(n=Count("customer")).order_by("-n"):
    mark = ""
    if d.n and d.ip_address.startswith("0.0.0.0"):
        mark = "   <-- PHANTOM: no real IP, created by the import"
    print(f"  {d.device_name:34} {d.ip_address:16} customers={d.n}{mark}")
print()
print("Real routers registered by staff:")
for d in MikrotikDevice.objects.exclude(ip_address="0.0.0.0"):
    print(f"  {d.device_name}")
