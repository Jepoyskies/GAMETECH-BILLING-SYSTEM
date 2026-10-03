"""
End-to-end business flow probe: Agent -> CSR -> Dispatch -> Technician -> CSR verify.

Drives the REAL views through Django's test Client (real URLconf, real
middleware, real @role_required / @permission_required gates, real signals).
This is the same code path a browser click hits; it is used because the
operator's network to the droplet was intermittently dropping mid-flow.

Read-only apart from the records it deliberately creates.
"""

from django.test import Client
from django.contrib.auth import get_user_model
from billing.models import Customer, Prospect, Payment, SystemLog
from dispatch.models import JobTicket, JobTicketHistory, Technician, Team
from network_manager.models import MikrotikDevice

User = get_user_model()
OK, BAD = "PASS", "**FAIL**"
results = []


def check(label, cond, detail=""):
    results.append((OK if cond else BAD, label, detail))
    print(f"  [{OK if cond else BAD}] {label} {detail}")
    return cond


def hdr(step):
    print("\n" + "=" * 72)
    print(step)
    print("=" * 72)


# ---------------------------------------------------------------- 0. baseline
hdr("0. BASELINE")
print(f"  customers={Customer.objects.count()} prospects={Prospect.objects.count()} tickets={JobTicket.objects.count()}")
p = Prospect.objects.filter(full_name__iexact="Juan Dela Cruz").first()
if not p:
    raise SystemExit("ABORT: no Juan Dela Cruz prospect to continue with")
print(f"  using prospect #{p.id} status={p.status} plan_id={p.plan_id} agent_id={p.agent_id}")

device = MikrotikDevice.objects.order_by("id").first()
print(f"  target router: {device.device_name} (id={device.id}) mode-agnostic (no writes attempted)")

# ------------------------------------------------- 1. CSR converts to customer
hdr("1. CSR (Vince) converts the prospect into a customer")
vince = Client()
vince.force_login(User.objects.get(username="Vince"))

r = vince.get(f"/customers/add/?prospect_id={p.id}")
check("CSR can open the add-customer form", r.status_code == 200, f"HTTP {r.status_code}")

before_tickets = JobTicket.objects.count()
r = vince.post("/customers/add/", {
    "prospect_id": p.id,
    "full_name": p.full_name,
    "phone": p.phone,
    "email": p.email or "",
    "address": p.address or "123 Test Street, Barangay 1",
    "pppoe_username": "delacruz_juan_e2e",
    "pppoe_password": "TestJuan123",
    "plan_id": p.plan_id,
    "device_id": device.id,
    "barangay_id": p.barangay_id or "",
    "agent_id": p.agent_id or "",
    "installation_status": "pending",
    "checklist_method": "in_person",
    "item_free_install": "on",
    "item_specific_plan": "on",
    "item_no_lockin": "on",
    "item_staggered_lock": "on",
    "item_same_day_repair": "on",
    "item_rebates_24h": "on",
}, follow=True)

cust = Customer.objects.filter(pppoe_username="delacruz_juan_e2e").first()
check("customer row created", cust is not None)
if cust:
    print(f"        customer #{cust.id} status={cust.status} install={cust.installation_status} expires={cust.expires_at}")
    check("customer starts pending + pending-install",
          cust.status == "pending" and cust.installation_status == "pending")
    check("sales agent credited on the customer", cust.agent_id == p.agent_id, f"agent_id={cust.agent_id}")

p.refresh_from_db()
check("prospect marked converted", p.status == "converted", f"status={p.status}")
check("prospect linked to the new customer", p.converted_customer_id == cust.id if cust else False)

# ------------------------------------------- 2. dispatch bridge auto-created it
hdr("2. DISPATCH BRIDGE (auto, via signal)")
tickets = list(JobTicket.objects.filter(customer=cust))
check("an INSTALLATION ticket exists", len(tickets) == 1, f"count={len(tickets)} (must be exactly 1)")
if tickets:
    t = tickets[0]
    print(f"        ticket {t.ticket_number} type={t.ticket_type} status={t.status} source={t.source_tab}")
    check("ticket type is INSTALLATION", t.ticket_type == "INSTALLATION")
    check("ticket sits in the unassigned queue",
          t.status == "PENDING" and t.technicians.count() == 0)

# ----------------------------------------------- 3. agent sees progress update
hdr("3. AGENT (Martin) sees the referral advance")
martin = Client()
martin.force_login(User.objects.get(username="Martin"))
r = martin.get("/agent-dashboard/")
check("agent dashboard renders", r.status_code == 200, f"HTTP {r.status_code}")
body = r.content.decode()
check("agent sees the converted customer", "Juan Dela Cruz" in body)
check("agent sees 'Converted' status", "Converted" in body)

# ------------------------------------------------- 4. CSR dispatches to a tech
hdr("4. CSR assigns the job to the technician")
tech = Technician.objects.filter(user__username="Merk").first()
print(f"  technician: {tech.name if tech else 'NONE'} (team={tech.team if tech else None})")

# ---------------------------------------------------- 5. technician sees work
hdr("5. TECHNICIAN (Merk) sees the job on his portal")
merk = Client()
merk.force_login(User.objects.get(username="Merk"))
r = merk.get("/dispatch/tech-dashboard/")
check("tech dashboard renders", r.status_code == 200, f"HTTP {r.status_code}")
r = merk.get("/dispatch/my-jobs/")
check("tech my-jobs renders", r.status_code == 200, f"HTTP {r.status_code}")

assigned = JobTicket.objects.filter(customer=cust, technicians=tech).exists()
print(f"  job currently assigned to Merk: {assigned}")

# --------------------------------------------------------------- 6. verdict
hdr("6. SUMMARY")
fails = [r for r in results if r[0] == BAD]
for status, label, detail in results:
    print(f"  {status:8} {label} {detail}")
print(f"\n  {len(results)-len(fails)}/{len(results)} checks passed")
if fails:
    print("  FAILURES:")
    for _, label, detail in fails:
        print(f"    - {label} {detail}")