"""Remove test residue created by this session's probes, then report the final
production state."""
from django.db.models import Q
from billing.models import (Customer, Payment, Prospect, SystemLog, Notification,
                            Rebate, CignalPlay, AddOnRequest, AuditLog,
                            AgentQualificationEvent, AgentPayoutBatch, CommissionTransaction)
from dispatch.models import JobTicket, JobTicketHistory, DispatchRecord, MonitoringRecord

TEST_PREFIXES = ("e2e_", "TEST ", "test_")

KEEP_USERNAMES = {"delacruz_juan_e2e"}


def go():
    print("=== BEFORE ===")
    print("  customers :", Customer.objects.count())
    print("  payments  :", Payment.objects.count())

    # 1. scratch customers (keep Juan Dela Cruz as the demo record)
    scratch = Customer.objects.exclude(pppoe_username__in=KEEP_USERNAMES).filter(
        Q(pppoe_username__startswith="e2e_") | Q(full_name__startswith="TEST ")
    )
    names = list(scratch.values_list("pppoe_username", flat=True))
    print(f"\n  scratch customers to remove: {names}")

    # 2. their payments -- Payment.customer is SET_NULL, so deleting the customer
    #    orphans the row. Remove the money too, it is all probe data.
    pn = Payment.objects.filter(username__in=names).delete()
    print(f"  scratch payments removed : {pn}")

    cn = scratch.delete()
    print(f"  scratch customers removed: {cn}")

    # 3. probe prospects / notifications / logs written by the probes
    for label, qs in (
        ("AgentQualificationEvent", AgentQualificationEvent.objects.filter(
            customer__pppoe_username__startswith="e2e_")),
        ("AgentPayoutBatch", AgentPayoutBatch.objects.all()),
        ("Prospect(not Juan)", Prospect.objects.exclude(
            full_name__iexact="Juan Dela Cruz")),
        ("CignalPlay", CignalPlay.objects.filter(
            customer__pppoe_username__startswith="e2e_")),
        ("AddOnRequest(test)", AddOnRequest.objects.filter(
            customer__pppoe_username__startswith="e2e_")),
        ("AuditLog(test)", AuditLog.objects.filter(
            customer__pppoe_username__startswith="e2e_")),
    ):
        n, _ = qs.delete()
        print(f"  {label:26} removed {n}")

    # 4. dispatch tickets for scratch customers
    JobTicketHistory.objects.filter(job_ticket__customer__pppoe_username__startswith="e2e_").delete()
    tn, _ = JobTicket.objects.filter(
        customer__pppoe_username__startswith="e2e_").delete()
    print(f"  {'JobTicket(test)':26} removed {tn}")

    print("\n=== FINAL STATE ===")
    from billing.models import Agent
    from dispatch.models import Technician
    from django.contrib.auth import get_user_model
    U = get_user_model()
    print("  customers :", Customer.objects.count())
    for c in Customer.objects.all():
        print(f"     {c.pppoe_username} | {c.full_name} | {c.status}/{c.installation_status}"
              f" | expires={c.expires_at} | device={c.mikrotik_device}")
    print("  payments  :", Payment.objects.count(),
          "| orphans:", Payment.objects.filter(customer__isnull=True).count())
    print("  tickets   :", JobTicket.objects.count())
    print("  prospects :", Prospect.objects.count())
    print("  users     :", sorted(U.objects.values_list("username", flat=True)))
    print("  agents    :", list(Agent.objects.values_list("name", "user__username")))
    print("  techs     :", list(Technician.objects.values_list("name", "user__username")))


go()