"""Final sweep: dispatch pipeline (QA / bounce-back / approval), analytics,
celery tasks, role-matrix enforcement, and error handling.
"""
import json
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from billing.models import (Customer, SubscriptionPlan, Payment, Rebate, SystemLog,
                            Notification, Agent, Prospect)
from dispatch.models import JobTicket, JobTicketHistory, Technician, Team

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)


admin = Client(); admin.force_login(U.objects.get(username="Jep"))
csr = Client(); csr.force_login(U.objects.get(username="Vince"))
tech = Client(); tech.force_login(U.objects.get(username="Merk"))

hdr("1. DISPATCH PIPELINE: assign -> arrive -> done -> QA bounce -> re-approve")
plan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()
tp = Technician.objects.filter(user__username="Merk").first()
c = Customer.objects.create(full_name="TEST Pipeline", pppoe_username="e2e_pipeline",
                            pppoe_password="x", status="active",
                            installation_status="installed", plan=plan, is_test_data=True)
t = JobTicket.objects.create(customer=c, client_name=c.full_name, ticket_type="INSTALLATION",
                             source_tab="INTERNET_INSTALL", status="PENDING",
                             priority="NORMAL", is_test_data=True)
print(f"  ticket {t.ticket_number} created ({JobTicket.objects.count()} total)")

r = csr.post(f"/dispatch/api/tickets/{t.id}/assign/",
             data=json.dumps({"technician_ids": [tp.id]}), content_type="application/json")
t.refresh_from_db()
check("assign works", t.status == "ASSIGNED", f"status={t.status}")

r = tech.post(f"/dispatch/api/tickets/{t.id}/arrived/", data=json.dumps({}),
              content_type="application/json")
t.refresh_from_db()
check("arrived works", t.status == "IN_PROGRESS", f"status={t.status}")

r = tech.post(f"/dispatch/api/tickets/{t.id}/complete/",
              data=json.dumps({"remarks": "installed"}), content_type="application/json")
t.refresh_from_db()
c.refresh_from_db()
check("tech done works", t.status == "COMPLETED", f"status={t.status}")
check("customer installed but NOT activated (awaiting payment)",
      c.installation_status == "installed" and c.status == "pending",
      f"status={c.status} install={c.installation_status}")

hdr("2. QA / BOUNCE-BACK")
hist_before = JobTicketHistory.objects.filter(job_ticket=t).count()
r = csr.post(f"/dispatch/api/tickets/{t.id}/qa/", data=json.dumps({"result": "bounce"}),
             content_type="application/json")
print(f"  POST /dispatch/api/tickets/{t.id}/qa/ -> {r.status_code}")
t.refresh_from_db()
hist_after = JobTicketHistory.objects.filter(job_ticket=t).count()
print(f"  status now={t.status} history {hist_before} -> {hist_after}")
check("QA recorded a history transition", hist_after > hist_before,
      f"{hist_before} -> {hist_after}")

hdr("3. ROLE MATRIX ENFORCEMENT")
matrix = [
    ("Vince", "CSR", "/admin-panel/", False),
    ("Vince", "CSR", "/staff/roles/", False),
    ("Vince", "CSR", "/customers/", True),
    ("Vince", "CSR", "/agents/", True),
    ("Martin", "Agent", "/customers/", False),
    ("Martin", "Agent", "/admin-panel/", False),
    ("Merk", "Technician", "/customers/", False),
    ("Jep", "Admin", "/admin-panel/", True),
    ("Jep", "Admin", "/staff/roles/", True),
]
for uname, role, url, should in matrix:
    cl = Client(); cl.force_login(U.objects.get(username=uname))
    r = cl.get(url)
    denied = r.status_code in (302, 403)
    ok = (not denied) if should else denied
    check(f"{role:11} {url:20} {'allow' if should else 'deny'}", ok, f"HTTP {r.status_code}")

hdr("4. ANALYTICS / REPORTING")
for url in ["/analytics/", "/reports/", "/subscriptions/", "/plans/",
            "/logs/payments/", "/payments/ledger/"]:
    r = admin.get(url)
    if r.status_code != 404:
        check(f"analytics page {url}", r.status_code == 200, f"HTTP {r.status_code}")
    else:
        print(f"  (no page at {url})")

hdr("5. CELERY TASK SAFETY")
from billing.celery import app as celery_app  # noqa
print(f"  celery app: {celery_app.main}")
try:
    conf = celery_app.conf.beat_schedule
    print(f"  beat schedule entries: {len(conf)}")
    for k in list(conf)[:10]:
        print(f"    {k}")
except Exception as e:
    print(f"  beat schedule unavailable: {e}")

hdr("6. ERROR HANDLING (no 500s anywhere)")
urls = ["/", "/customers/", "/customers/add/", "/plans/", "/subscriptions/",
        "/dispatch/queue/", "/dispatch/dashboard/", "/agents/", "/prospects/",
        "/cignal-dashboard/", "/devices/devices/", "/live-monitoring/",
        "/admin-panel/", "/staff/roles/", "/agents/payouts/",
        "/payments/", "/add-ons/", "/logs/payments/"]
bad = []
for u in urls:
    r = admin.get(u)
    if r.status_code >= 500:
        bad.append((u, r.status_code))
        print(f"  **500** {u}")
check("no page returns 5xx", not bad, f"bad={bad}")

hdr("7. DATA INTEGRITY")
check("no negative payments", Payment.objects.filter(amount__lt=0).count() == 0)
check("no negative rebates", Rebate.objects.filter(amount__lt=0).count() == 0)
check("no orphan payments", Payment.objects.filter(customer__isnull=True).count() == 0)
check("no customers with empty username",
      Customer.objects.filter(pppoe_username="").count() == 0)
check("installed customers without any ticket",
      Customer.objects.filter(installation_status="installed")
            .exclude(id__in=JobTicket.objects.values("customer_id")).count() == 0,
      f"count={Customer.objects.filter(installation_status='installed').exclude(id__in=JobTicket.objects.values('customer_id')).count()}")

JobTicketHistory.objects.filter(job_ticket=t).delete()
t.delete()
Customer.objects.filter(pppoe_username="e2e_pipeline").delete()

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")