"""
One-shot operational reset. Keeps staff + reference data, drops all
transactional data so the Agent -> CSR -> Technician -> CSR flow can be
re-tested from a clean slate.

Run via:  docker exec -i gametech-web python manage.py shell < wipe_operational_data.py

WHY THE MIKROTIK SIGNAL IS DISCONNECTED
----------------------------------------
billing.signals.delete_customer_from_mikrotik fires on Customer post_delete and
calls the router API once per row. Bulk-deleting 2,041 customers would fire
2,041 sequential socket calls against FOUR LIVE routers that still have real
subscribers on them. That hangs for hours and risks cutting paying customers
off. We disconnect it for the duration and leave router state untouched, so the
"which PPPoE users actually exist on the routers" reconciliation can still be
done afterwards.

KEEP = staff (Jep, Jill, Admin, Vince, Martin, Merk) + reference data
     (plans, barangays, account types, roles, routers, teams, config).
DROP = customers, money, dispatch work, prospects, logs.
"""

from django.db import transaction
from django.db.models.signals import post_delete
from django.contrib.auth import get_user_model

from billing.models import (
    Customer, Payment, Rebate, CignalPlay, AddOnRequest, CustomerAgentHistory,
    CustomerMacHistory, ChecklistConfirmation, Prospect, CommissionTransaction,
    AgentPayoutBatch, AgentQualificationEvent, JobOrder, AuditLog as BillingAuditLog,
    SystemLog, SmsLog, Notification, ImprovementRequest, Agent,
)
from dispatch.models import (
    JobTicket, JobTicketHistory, TicketBounceHistory, CallAttemptLog,
    DispatchRecord, MonitoringRecord, JobDetail, AuditLog as DispatchAuditLog,
    Technician,
)
from billing.signals import delete_customer_from_mikrotik

User = get_user_model()

# EXACT case matters. auth_user.username is stored capitalised ("Jep", not
# "jep"). A previous run of this script used a lowercase keep-set, so
# `exclude(username__in=...)` matched nothing and deleted EVERY user including
# all staff. Never use case-insensitive matching here by accident.
KEEP_USERNAMES = {"Jep", "Jill", "Admin", "Vince", "Martin", "Merk"}


def preflight():
    """Refuse to run unless every account we intend to keep actually exists.

    This is the guard that would have caught the case-mismatch bug before any
    row was touched.
    """
    present = set(User.objects.values_list("username", flat=True))
    missing = KEEP_USERNAMES - present
    print("preflight: users present =", sorted(present))
    if missing:
        raise SystemExit(f"ABORT: these staff accounts do not exist: {sorted(missing)}")
    doomed = sorted(present - KEEP_USERNAMES)
    print(f"preflight: keeping {len(KEEP_USERNAMES)} staff, would delete {doomed}")
    for name in sorted(KEEP_USERNAMES):
        u = User.objects.get(username=name)
        print(f"    keep {name:8} id={u.id} staff={u.is_staff} super={u.is_superuser}")
    return doomed


def wipe():
    doomed = preflight()

    print("Disconnecting Customer post_delete (MikroTik API) for the duration...")
    post_delete.disconnect(delete_customer_from_mikrotik, sender=Customer)

    try:
        with transaction.atomic():
            # --- dispatch work first (children of Customer) ---
            for model in (
                JobTicketHistory, TicketBounceHistory, CallAttemptLog,
                JobTicket, JobDetail, DispatchRecord, MonitoringRecord,
                DispatchAuditLog,
            ):
                n, _ = model.objects.all().delete()
                print(f"  deleted {model.__name__:24} {n}")

            # --- money + billing side ---
            for model in (
                AgentQualificationEvent, CommissionTransaction, AgentPayoutBatch,
                Payment, Rebate, CignalPlay, AddOnRequest, CustomerAgentHistory,
                CustomerMacHistory, ChecklistConfirmation, Prospect, JobOrder,
                BillingAuditLog,
            ):
                n, _ = model.objects.all().delete()
                print(f"  deleted {model.__name__:24} {n}")

            # --- customers last ---
            n, _ = Customer.objects.all().delete()
            print(f"  deleted {'Customer':24} {n}")

            # --- logs / noise ---
            for model in (SystemLog, SmsLog, Notification, ImprovementRequest):
                n, _ = model.objects.all().delete()
                print(f"  deleted {model.__name__:24} {n}")

            # --- non-staff users, matched EXACTLY against the doomed list ---
            for name in doomed:
                u = User.objects.filter(username=name).first()
                if u:
                    print(f"  removing user {name} (id={u.id})")
                    u.delete()

            # test personas that are not the real staff
            n, _ = Technician.objects.exclude(
                user__username__in=KEEP_USERNAMES).delete()
            print(f"  deleted {'Technician(test)':24} {n}")

    finally:
        post_delete.connect(delete_customer_from_mikrotik, sender=Customer)
        print("Reconnected Customer post_delete.")

    print("\n=== VERIFY ===")
    from billing.models import SubscriptionPlan, Barangay
    from network_manager.models import MikrotikDevice
    print("  Customer          :", Customer.objects.count())
    print("  Payment           :", Payment.objects.count())
    print("  JobTicket         :", JobTicket.objects.count())
    print("  Prospect          :", Prospect.objects.count())
    print("  SystemLog         :", SystemLog.objects.count())
    print("  Users             :", sorted(User.objects.values_list("username", flat=True)))
    print("  Technicians       :", list(Technician.objects.values_list("name", "user__username")))
    print("  Agents            :", list(Agent.objects.values_list("name", "user__username")))
    print("  Plans kept        :", SubscriptionPlan.objects.count())
    print("  Barangays kept    :", Barangay.objects.count())
    print("  Routers kept      :", MikrotikDevice.objects.count())

    survivors = set(User.objects.values_list("username", flat=True))
    lost = KEEP_USERNAMES - survivors
    if lost:
        raise SystemExit(f"FATAL: staff lost during wipe: {sorted(lost)}")
    print("\nAll staff survived.")


wipe()