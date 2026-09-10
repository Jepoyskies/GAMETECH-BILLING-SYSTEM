import os, django, traceback
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gametech_core.settings")
os.environ['DEBUG'] = 'True'
django.setup()

from django.test.client import Client
from django.contrib.auth.models import User
from billing.models import Customer

c = Client()
user = User.objects.first()
c.force_login(user)

# Get a real customer ID
cust = Customer.objects.first()
cust_id = cust.id if cust else 1

# All URLs to test
urls = [
    ("/", "Dashboard"),
    ("/customers/", "Customer List"),
    (f"/customers/view/{cust_id}/", "View Customer"),
    ("/customers/add/", "Add Customer"),
    (f"/customers/edit/{cust_id}/", "Edit Customer"),
    ("/live-monitoring/", "Live Monitoring"),
    ("/plans/", "Plans"),
    ("/service-plans/", "Service Plans"),
    ("/subscription-plans/", "Subscription Plans"),
    ("/agents/", "Agents"),
    ("/agents/add/", "Add Agent"),
    ("/staff/", "Staff & Admins"),
    ("/staff/add/", "Add Staff"),
    ("/payment-logs/", "Payment Logs"),
    ("/payment-portal/", "Payment Portal"),
    ("/sms/", "SMS Messaging"),
    ("/message-templates/", "Message Templates"),
    ("/settings/", "Settings"),
    ("/profile/", "Profile"),
    ("/change-password/", "Change Password"),
    ("/logs/", "System Logs"),
    ("/analytics/", "Analytics"),
    ("/geomap/", "Geo Map"),
    ("/cignal-play/", "Cignal Play List"),
    ("/admin-panel/", "Admin Panel"),
    ("/changelog/", "Changelog"),
    ("/notifications/", "Notifications"),
    ("/improvement-requests/", "Improvement Requests"),
    ("/rebates-logs/", "Rebates Logs"),
    ("/downdetector/", "Down Detector"),
    ("/auto-suspend/", "Auto Suspend"),
    ("/import-data/", "Import Data"),
    ("/payment-addon-logs/", "Payment Addon Logs"),
    ("/mikrotik-active-users/", "Mikrotik Active Users"),
]

print("=" * 70)
print("FULL SYSTEM PAGE TEST")
print("=" * 70)

errors = []
successes = []

for url, name in urls:
    try:
        response = c.get(url)
        status = response.status_code
        if status >= 500:
            errors.append((name, url, status, "Server Error"))
            print(f"  FAIL  {name:30s} {url:40s} -> {status}")
        elif status >= 400:
            errors.append((name, url, status, "Client Error"))
            print(f"  WARN  {name:30s} {url:40s} -> {status}")
        elif status >= 300:
            successes.append((name, url, status))
            print(f"  OK    {name:30s} {url:40s} -> {status} (redirect)")
        else:
            successes.append((name, url, status))
            print(f"  OK    {name:30s} {url:40s} -> {status}")
    except Exception as e:
        errors.append((name, url, 0, str(e)[:200]))
        print(f"  CRASH {name:30s} {url:40s} -> EXCEPTION: {str(e)[:100]}")

print()
print("=" * 70)
print(f"RESULTS: {len(successes)} OK, {len(errors)} ERRORS")
print("=" * 70)

if errors:
    print("\nFAILED PAGES:")
    for name, url, status, msg in errors:
        print(f"  - {name} ({url}) -> {status}: {msg}")

# Now get detailed tracebacks for 500 errors
print("\n" + "=" * 70)
print("DETAILED ERROR TRACEBACKS")
print("=" * 70)
for name, url, status, msg in errors:
    if status >= 500 or status == 0:
        print(f"\n--- {name} ({url}) ---")
        try:
            response = c.get(url)
            if response.status_code >= 500:
                content = response.content.decode('utf-8', errors='replace')
                # Extract just the exception info from Django debug page
                if 'Exception Type' in content:
                    start = content.find('Exception Type')
                    end = content.find('Request information')
                    if end == -1:
                        end = start + 500
                    print(content[start:end][:500])
                else:
                    print(content[:500])
        except Exception as e:
            traceback.print_exc()
