from billing.models import Customer, SubscriptionPlan

print("=" * 74)
print("THE 4 REMAINING GROUPS -- do they differ in UPLOAD speed?")
print("=" * 74)
names = [
    ["GTipid Fiber 1000", "GTipid Fiber 1000 (Speedboost)"],
    ["GTipid Fiber 1300", "GTipid Fiber 1300 (Speedboost)"],
    ["GTipid Fiber 1500", "GTipid Fiber 1500 (Speedboost)"],
    ["GIMI Home Fiber 1500", "GIMI Home Fiber 1500 (New Plan)",
     "GIMI Home Fiber 1500 (100 Mbps)"],
]
for group in names:
    print()
    for n in group:
        p = SubscriptionPlan.objects.filter(name=n).first()
        if not p:
            print(f"  {n:<34} MISSING")
            continue
        c = Customer.objects.filter(plan=p).count()
        print(f"  {n:<34} up={p.speed_up:<12} down={p.speed_down:<12} "
              f"price={p.price:<9} customers={c}")
    ups = {SubscriptionPlan.objects.filter(name=n).first().speed_up
           for n in group if SubscriptionPlan.objects.filter(name=n).first()}
    downs = {SubscriptionPlan.objects.filter(name=n).first().speed_down
             for n in group if SubscriptionPlan.objects.filter(name=n).first()}
    if len(ups) > 1 or len(downs) > 1:
        print(f"  -> DISTINCT products (up or down differ): up={sorted(ups)} "
              f"down={sorted(downs)}")
    else:
        print(f"  -> TRUE duplicates: identical up AND down {sorted(ups)}")
print("=" * 74)