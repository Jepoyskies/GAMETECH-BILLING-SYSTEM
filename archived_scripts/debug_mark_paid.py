from django.contrib.auth import get_user_model
from billing.models import Agent, AgentQualificationEvent, AgentPayoutBatch, SubscriptionPlan
from billing.services.incentives import create_agent_payout_batch
from billing.services.payouts import mark_agent_payout_batch_paid
from django.utils import timezone
from datetime import timedelta

U = get_user_model()


def go():
    agent = Agent.objects.filter(user__username="Martin").first()
    plan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()
    c = Customer = None
    from billing.models import Customer as C
    cust = C.objects.create(
        full_name="TEST markpaid", pppoe_username="e2e_markpaid", pppoe_password="x",
        status="active", installation_status="installed", plan=plan,
        agent=agent, original_agent=agent, is_test_data=True)
    C.objects.filter(pk=cust.pk).update(expires_at=timezone.now() + timedelta(days=20))
    ev = AgentQualificationEvent.objects.filter(customer=cust).count()
    print("existing events:", ev)

    # force-create a qualification event so we have something to batch
    if not ev:
        from billing.services.incentives import evaluate_agent_qualification
        staff = Client_login()
        staff.post(f"/customer/{cust.pppoe_username}/pay/",
                   {"amount": str(plan.price), "payment_method": "cash", "reason": "m1"})
        staff.post(f"/customer/{cust.pppoe_username}/pay/",
                   {"amount": str(plan.price), "payment_method": "cash", "reason": "m2"})
        print("after payments, events:", AgentQualificationEvent.objects.filter(customer=cust).count())

    # top up to batch_size
    bs = 5
    for i in range(6):
        if AgentQualificationEvent.objects.filter(agent=agent, status="qualified",
                                                 payout_batch__isnull=True).count() >= bs:
            break
        u2 = f"e2e_mp_{i}"
        cc = C.objects.create(full_name=f"TEST mp {i}", pppoe_username=u2, pppoe_password="x",
                              status="active", installation_status="installed", plan=plan,
                              agent=agent, original_agent=agent, is_test_data=True)
        C.objects.filter(pk=cc.pk).update(expires_at=timezone.now() + timedelta(days=20))
        s = Client_login()
        s.post(f"/customer/{u2}/pay/", {"amount": str(plan.price), "payment_method": "cash", "reason": "m1"})
        s.post(f"/customer/{u2}/pay/", {"amount": str(plan.price), "payment_method": "cash", "reason": "m2"})

    batch = create_agent_payout_batch(agent, user=U.objects.get(username="Jep"))
    print("batch:", batch.batch_number, batch.status, batch.amount)

    print("\n--- calling mark_agent_payout_batch_paid directly ---")
    try:
        out = mark_agent_payout_batch_paid(
            batch=batch, user=U.objects.get(username="Jep"),
            reference_no="E2E-REF-1", notes="test")
        print("returned:", out)
    except Exception as e:
        import traceback
        print("EXCEPTION:", type(e).__name__, e)
        traceback.print_exc()

    batch.refresh_from_db()
    print("batch after:", batch.status, "paid_at:", batch.paid_at)

    AgentQualificationEvent.objects.filter(customer__pppoe_username__startswith="e2e_").delete()
    C.objects.filter(pppoe_username__startswith="e2e_").delete()
    batch.delete()


def Client_login():
    from django.test import Client
    from django.contrib.auth import get_user_model
    c = Client()
    c.force_login(get_user_model().objects.get(username="Vince"))
    return c


go()