import json, collections
d = json.load(open("/app/billing/data/last_import_report.json"))
print("=== IMPORT REPORT ===")
for k in ("total_customers", "pppoe_credentials"):
    print(f"  {k:22} {d.get(k)}")
print(f"  zero_date_customers   {len(d.get('zero_date_customers', []))}")
print(f"  missing_password      {len(d.get('missing_password_customers', []))}")
print(f"  unmapped_statuses     {d.get('unmapped_statuses', '(none - all statuses valid)')}")
print(f"  devices_created       {d.get('devices_created')}")
print(f"  payments              {d.get('payments')}")