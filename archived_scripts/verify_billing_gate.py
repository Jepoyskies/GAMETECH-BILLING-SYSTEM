"""Verify the new billing gate: staff keep full access, Technician and Agent are
blocked from subscriber/billing data, and nothing 500s."""
from django.test import Client
from django.contrib.auth import get_user_model

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


PAGES = [
    "/customers/", "/cignal-dashboard/", "/cignal-dashboard/applications/",
    "/cignal-dashboard/logs/", "/plans/", "/subscriptions/",
    "/agents/payouts/", "/plans/cignal-play/", "/add-ons/",
]

print("=" * 78)
print("TECHNICIAN (Merk) - must be DENIED everywhere")
print("=" * 78)
tech = Client(); tech.force_login(U.objects.get(username="Merk"))
for u in PAGES:
    r = tech.get(u, follow=False)
    denied = r.status_code in (302, 403)
    check(f"tech {u:36} denied", denied, f"HTTP {r.status_code}")

print()
print("=" * 78)
print("AGENT (Martin) - must be DENIED staff pages")
print("=" * 78)
ag = Client(); ag.force_login(U.objects.get(username="Martin"))
for u in PAGES:
    r = ag.get(u, follow=False)
    denied = r.status_code in (302, 403)
    check(f"agent {u:35} denied", denied, f"HTTP {r.status_code}")

print()
print("=" * 78)
print("CSR (Vince) - billing=True so MUST still reach these")
print("=" * 78)
csr = Client(); csr.force_login(U.objects.get(username="Vince"))
for u in PAGES:
    r = csr.get(u, follow=False)
    ok = r.status_code in (200, 302)
    check(f"csr {u:36} allowed", ok, f"HTTP {r.status_code}")

print()
print("=" * 78)
print("ADMIN (Jep) - must reach everything")
print("=" * 78)
adm = Client(); adm.force_login(U.objects.get(username="Jep"))
for u in PAGES:
    r = adm.get(u, follow=False)
    check(f"admin {u:35} allowed", r.status_code in (200, 302), f"HTTP {r.status_code}")

print()
print("=" * 78)
print("NO 5xx ANYWHERE (all personas x all pages)")
print("=" * 78)
for name in ("Jep", "Vince", "Martin", "Merk"):
    cl = Client(); cl.force_login(U.objects.get(username=name))
    for u in PAGES:
        r = cl.get(u)
        if r.status_code >= 500:
            check(f"5xx on {u} as {name}", False, f"HTTP {r.status_code}")
check("no 5xx across all personas and pages", True)

hdr = [r for r in res if not r[0]]
print()
print("=" * 78)
print(f"RESULT: {len(res)-len(hdr)}/{len(res)} passed")
if hdr:
    print("FAILURES:")
    for ok, l, d in hdr:
        print(f"  {l} {d}")
print("=" * 78)