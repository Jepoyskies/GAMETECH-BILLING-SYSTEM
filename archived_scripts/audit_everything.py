"""
Whole-system audit: what is actually unfinished?

Sweeps EVERY named URL in the project with an admin session and records the
status code, then checks data integrity, the plan catalogue, and leftover test
residue. Read-only.
"""
import re
from collections import Counter, defaultdict

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from billing.models import (
    Agent, Customer, Payment, Prospect, SubscriptionPlan, Notification,
    SystemLog, Barangay,
)
from dispatch.models import JobTicket
from billing.services.plan_health import plan_health

U = get_user_model()


def named_urls(resolver=None, prefix=""):
    """Every named route in the project, with a concrete sample URL."""
    resolver = resolver or get_resolver()
    out = []

    def walk(r, prefix):
        for p in r.url_patterns:
            if isinstance(p, URLResolver):
                try:
                    m = prefix + str(p.pattern)
                except Exception:
                    continue
                walk(p, m)
            elif isinstance(p, URLPattern):
                if p.name:
                    out.append((p.name, prefix + str(p.pattern)))
    walk(resolver, prefix)
    return out


def concrete(pattern):
    """Turn 'agents/view/<int:agent_id>/' into a URL that will resolve."""
    agent_id = 19
    dev_id = 1
    cust_id = 2128
    ticket_id = 1
    sub = {
        "agent_id": agent_id, "device_id": dev_id, "customer_id": cust_id,
        "id": cust_id, "pk": cust_id, "ticket_id": ticket_id,
        "prospect_id": 1, "plan_id": 1, "batch_id": 1, "month": "10",
        "year": "2026", "barangay_id": 1, "user_id": 1, "staff_id": 1,
        "notification_id": 1, "record_id": 1, "job_id": 1, "tech_id": 1,
        "team_id": 1, "otp_id": 1, "payment_id": 1, "invoice_id": 1,
        "subscription_id": 1, "addon_id": 1, "cignal_id": 1, "number": "1",
        "slug": "x", "token": "x", "pk_id": 1,
    }
    pat = pattern
    for k, v in sub.items():
        pat = pat.replace(f"<int:{k}>", str(v))
        pat = pat.replace(f"<str:{k}>", str(v))
        pat = pat.replace(f"<slug:{k}>", str(v))
        pat = pat.replace(f"<uuid:{k}>", "00000000-0000-0000-0000-000000000000")
    pat = re.sub(r"<[a-zA-Z_:]+\:?[^>]*>", "1", pat)
    return pat


print("=" * 78)
print("1. ROUTE SWEEP -- every named URL, as an admin")
print("=" * 78)
adm = Client()
adm.force_login(U.objects.get(username="Jep"))

routes = named_urls()
print(f"named routes found: {len(routes)}")

results = []
for name, pattern in sorted(routes):
    url = concrete(pattern)
    if not url.startswith("/"):
        url = "/" + url
    if url.count("/") > 4:
        continue
    try:
        r = adm.get(url, follow=False)
        code = r.status_code
    except Exception as e:
        code = f"EXC:{type(e).__name__}"
    results.append((code, name, url))

by_code = Counter(str(c) for c, _, _ in results)
print()
for code, n in sorted(by_code.items()):
    print(f"  {code:>10} : {n}")

broken = [x for x in results if str(x[0]).startswith(("4", "5", "EXC"))]
print()
print(f"--- routes NOT returning 2xx/3xx ({len(broken)}) ---")
for code, name, url in sorted(broken, key=lambda x: str(x[0])):
    print(f"  {str(code):>6}  {name:<38} {url}")

print()
print("=" * 78)
print("2. 5xx ONLY -- these are real bugs, not just missing records")
print("=" * 78)
errs = [x for x in results if str(x[0]).startswith("5") or str(x[0]).startswith("EXC")]
if not errs:
    print("  none")
for code, name, url in errs:
    print(f"  {str(code):>6}  {name:<38} {url}")

print()
print("=" * 78)
print("3. DATA INTEGRITY")
print("=" * 78)
checks = [
    ("customers with a duplicate pppoe_username",
     Customer.objects.count() - Customer.objects.exclude(
         pppoe_username__isnull=True).values("pppoe_username").distinct().count()),
    ("customers with no plan", Customer.objects.filter(plan__isnull=True).count()),
    ("installed customers with NO expiry date",
     Customer.objects.filter(installation_status="installed",
                            expires_at__isnull=True).count()),
    ("pending-install customers already marked active",
     Customer.objects.filter(installation_status="pending",
                            status="active").count()),
    ("customers pointing at a device with no IP",
     Customer.objects.filter(mikrotik_device__ip_address="0.0.0.0").count()),
    ("payments with no customer",
     Payment.objects.filter(customer__isnull=True).count()),
    ("job tickets with no customer",
     JobTicket.objects.filter(customer__isnull=True).count()),
    ("open tickets for a customer with no agent",
     JobTicket.objects.filter(status__in=["PENDING", "ASSIGNED"],
                              customer__agent__isnull=True).count()),
    ("orphan notifications (link to a missing customer)",
     sum(1 for n in Notification.objects.all()
         if (m := re.search(r"/customers/(\d+)", n.link or ""))
         and not Customer.objects.filter(id=int(m.group(1))).exists())),
    ("prospects still open", Prospect.objects.exclude(
        status="converted").count()),
]
for label, n in checks:
    print(f"  {n:>5}  {label}")

print()
print("=" * 78)
print("4. TEST RESIDUE")
print("=" * 78)
print(f"  notifications : {Notification.objects.count()}")
print(f"  systemlogs    : {SystemLog.objects.count()}")
print(f"  by action     : "
      f"{dict(Counter(SystemLog.objects.values_list('action', flat=True)).most_common(6))}")
print(f"  customers     : {Customer.objects.count()}")
for c in Customer.objects.all():
    print(f"      {c.pppoe_username} | {c.full_name} | agent={c.agent} "
          f"| {c.status}/{c.installation_status}")

print()
print("=" * 78)
print("5. PLAN CATALOGUE")
print("=" * 78)
h = plan_health()
print(f"  {h['total_plans']} plans, {h['plans_with_profile']} mapped")
print(f"  {len(h['ambiguous'])} price collisions, {len(h['unmapped'])} unmapped")
print()
inuse = set(Customer.objects.filter(plan__isnull=False)
            .values_list("plan__name", flat=True))
unmapped_inuse = {u["name"] for u in h["unmapped"]} & inuse
print(f"  unmapped but IN USE: {sorted(unmapped_inuse) or 'none'}")

print()
print("=" * 78)
print("6. REFERENCE DATA")
print("=" * 78)
print(f"  agents    : {Agent.objects.count()}")
print(f"  barangays : {Barangay.objects.count()}")
print(f"  plans     : {SubscriptionPlan.objects.count()}")
