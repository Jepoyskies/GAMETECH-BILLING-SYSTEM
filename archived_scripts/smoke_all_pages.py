"""Smoke every page as every persona. Read-only. Reports status codes + exceptions."""
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse, NoReverseMatch

User = get_user_model()

PERSONAS = {
    "Admin": ("Jep", [
        "/", "/customers/", "/customers/add/", "/subscriptions/", "/plans/",
        "/payments/", "/logs/payments/", "/add-ons/", "/cignal-dashboard/",
        "/cignal-dashboard/applications/", "/cignal-dashboard/logs/",
        "/live-monitoring/", "/devices/devices/", "/mikrotik-active-users/",
        "/geomap/", "/devices/winbox/", "/downdetector/",
        "/dispatch/dashboard/", "/dispatch/queue/", "/dispatch/monitoring/",
        "/dispatch/internet-install/", "/dispatch/cignal-install/",
        "/dispatch/client-concerns/", "/dispatch/map/", "/dispatch/management/",
        "/dispatch/audit-log/", "/agents/", "/prospects/",
        "/admin-panel/", "/staff/roles/", "/staff/",
        "/dispatch/tech-dashboard/", "/dispatch/my-jobs/",
        "/agent-dashboard/", "/profile/",
    ]),
    "CSR": ("Vince", [
        "/", "/customers/", "/customers/add/", "/subscriptions/", "/plans/",
        "/payments/", "/logs/payments/", "/add-ons/",
        "/dispatch/dashboard/", "/dispatch/queue/", "/dispatch/monitoring/",
        "/dispatch/internet-install/", "/dispatch/client-concerns/",
        "/dispatch/map/", "/agents/", "/prospects/", "/admin-panel/",
        "/staff/roles/", "/staff/manage-roles/",
    ]),
    "Agent": ("Martin", ["/agent-dashboard/", "/agent-dashboard/add/", "/profile/"]),
    "Technician": ("Merk", ["/dispatch/tech-dashboard/", "/dispatch/my-jobs/", "/profile/"]),
}

total = ok = denied = err = 0
problems = []

for persona, (username, urls) in PERSONAS.items():
    print("\n" + "=" * 74)
    print(f"{persona}  (as {username})")
    print("=" * 74)
    c = Client()
    c.force_login(User.objects.get(username=username))
    for u in urls:
        total += 1
        try:
            r = c.get(u, follow=False)
            code = r.status_code
            if code in (200, 302):
                # 302 to /login/ means the session was rejected
                loc = r.headers.get("Location", "")
                if code == 302 and loc.rstrip("/") in ("/login", ""):
                    denied += 1
                    problems.append((persona, u, "redirected to login"))
                    print(f"  {code}  {u:42} -> bounced to login")
                else:
                    ok += 1
                    print(f"  {code}  {u:42}")
            elif code in (401, 403):
                denied += 1
                problems.append((persona, u, f"HTTP {code} (permission)"))
                print(f"  {code}  {u:42} <-- PERMISSION DENIED")
            elif code == 404:
                err += 1
                problems.append((persona, u, "HTTP 404"))
                print(f"  {code}  {u:42} <-- NOT FOUND")
            else:
                err += 1
                problems.append((persona, u, f"HTTP {code}"))
                print(f"  {code}  {u:42} <-- UNEXPECTED")
        except Exception as e:
            err += 1
            problems.append((persona, u, f"{type(e).__name__}: {str(e)[:90]}"))
            print(f"  EXC {u:42} <-- {type(e).__name__}: {str(e)[:70]}")

print("\n" + "=" * 74)
print(f"TOTAL {total} | reachable {ok} | denied {denied} | errors {err}")
print("=" * 74)
if problems:
    print("\nPROBLEMS:")
    for persona, u, why in problems:
        print(f"  [{persona:10}] {u:42} {why}")
else:
    print("\nNo problems.")