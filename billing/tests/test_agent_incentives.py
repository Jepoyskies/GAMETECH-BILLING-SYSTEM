from decimal import Decimal
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from billing.models import (
    Customer,
    Agent,
    SubscriptionPlan,
    Payment,
    AgentQualificationEvent,
    AgentPayoutBatch,
    IncentiveSetting,
    Prospect,
)
from billing.services.incentives import (
    get_customer_qualifying_paid_total,
    evaluate_agent_qualification,
    create_agent_payout_batch,
    mark_agent_payout_batch_paid,
    get_agent_incentive_summary,
)


class AgentIncentiveEngineTests(TestCase):
    """
    Test suite for Phase 5B: Agent Incentive Engine (SPEC Decision 7).
    Covers qualification detection, rollback revocation, idempotency,
    batch creation in multiples of 5, carry-over, permissions, and agent isolation.
    """

    def setUp(self):
        # 1. Incentive Settings
        self.settings = IncentiveSetting.get_settings()
        self.settings.incentive_amount = Decimal("500.00")
        self.settings.batch_size = 5
        self.settings.lock_days = 60
        self.settings.save()

        # 2. Subscription Plan
        self.plan = SubscriptionPlan.objects.create(
            name="Plan 1000",
            speed_up="50 Mbps",
            speed_down="50 Mbps",
            price=Decimal("1000.00"),
            validity_days=30,
        )

        # 3. Agents
        self.agent_user_a = User.objects.create_user(
            username="agent_a", password="password123", email="agent_a@test.com"
        )
        self.agent_a = Agent.objects.create(
            user=self.agent_user_a,
            name="Agent Alpha",
            email="agent_a@test.com",
            is_test_data=True,
        )

        self.agent_user_b = User.objects.create_user(
            username="agent_b", password="password123", email="agent_b@test.com"
        )
        self.agent_b = Agent.objects.create(
            user=self.agent_user_b,
            name="Agent Beta",
            email="agent_b@test.com",
            is_test_data=True,
        )

        # 4. Admin and Staff Users
        self.admin_user = User.objects.create_superuser(
            username="admin_user", password="password123", email="admin@test.com"
        )

        self.staff_unpermitted = User.objects.create_user(
            username="staff_regular", password="password123", email="staff@test.com", is_staff=True
        )

        self.staff_permitted = User.objects.create_user(
            username="staff_payout", password="password123", email="payout_staff@test.com", is_staff=True
        )
        # Grant billing.mark_payout_paid
        cust_ct = ContentType.objects.get_for_model(Customer)
        payout_perm, _ = Permission.objects.get_or_create(
            codename="mark_payout_paid",
            content_type=cust_ct,
            defaults={"name": "Can approve and mark agent payout batches as paid"},
        )
        self.staff_permitted.user_permissions.add(payout_perm)

        self.client = Client()

    def _create_customer(self, name, agent, pppoe, source="agent", status="active", installation_status="installed"):
        return Customer.objects.create(
            full_name=name,
            pppoe_username=pppoe,
            phone="09171234567",
            plan=self.plan,
            agent=agent,
            original_agent=agent,
            source=source,
            status=status,
            installation_status=installation_status,
            is_test_data=True,
        )

    # 1. Second-month payment
    def test_second_month_payment_qualifies_customer(self):
        cust = self._create_customer("Subscriber 1", self.agent_a, "sub1")

        # Month 1 payment
        p1 = Payment.objects.create(
            customer=cust,
            username=cust.pppoe_username,
            amount=Decimal("1000.00"),
            payment_method="Cash",
            paid_at=timezone.now(),
        )
        self.assertEqual(get_customer_qualifying_paid_total(cust), Decimal("1000.00"))
        self.assertEqual(AgentQualificationEvent.objects.filter(customer=cust).count(), 0)

        # Month 2 payment (qualifying)
        p2 = Payment.objects.create(
            customer=cust,
            username=cust.pppoe_username,
            amount=Decimal("1000.00"),
            payment_method="Cash",
            paid_at=timezone.now() + timezone.timedelta(days=30),
        )
        self.assertEqual(get_customer_qualifying_paid_total(cust), Decimal("2000.00"))
        
        event = AgentQualificationEvent.objects.filter(customer=cust).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.status, "qualified")
        self.assertEqual(event.agent, self.agent_a)
        self.assertEqual(event.qualifying_amount, Decimal("500.00"))

    # 2. 2-month advance
    def test_two_month_advance_at_or_after_install(self):
        cust = self._create_customer("Subscriber 2", self.agent_a, "sub2")

        # Advance payment of ₱2,000 upfront
        p = Payment.objects.create(
            customer=cust,
            username=cust.pppoe_username,
            amount=Decimal("2000.00"),
            payment_method="GCash",
            paid_at=timezone.now(),
        )
        self.assertEqual(get_customer_qualifying_paid_total(cust), Decimal("2000.00"))
        
        event = AgentQualificationEvent.objects.filter(customer=cust).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.status, "qualified")

    # 3. Cumulative partial payments
    def test_cumulative_partial_payments_qualify(self):
        cust = self._create_customer("Subscriber 3", self.agent_a, "sub3")

        # Month 1 install: ₱1,000
        Payment.objects.create(
            customer=cust, username=cust.pppoe_username, amount=Decimal("1000.00"), payment_method="Cash"
        )
        self.assertEqual(AgentQualificationEvent.objects.filter(customer=cust).count(), 0)

        # Partial payment 1: ₱400
        Payment.objects.create(
            customer=cust, username=cust.pppoe_username, amount=Decimal("400.00"), payment_method="Cash"
        )
        self.assertEqual(get_customer_qualifying_paid_total(cust), Decimal("1400.00"))
        self.assertEqual(AgentQualificationEvent.objects.filter(customer=cust).count(), 0)

        # Partial payment 2: ₱600 (reaches ₱2,000 total)
        Payment.objects.create(
            customer=cust, username=cust.pppoe_username, amount=Decimal("600.00"), payment_method="Cash"
        )
        self.assertEqual(get_customer_qualifying_paid_total(cust), Decimal("2000.00"))

        event = AgentQualificationEvent.objects.filter(customer=cust).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.status, "qualified")

    # 4. One-time fee excluded
    def test_one_time_fee_excluded_from_qualification(self):
        cust = self._create_customer("Subscriber 4", self.agent_a, "sub4")

        # Payment of ₱1,500 includes ₱500 one-time upgrade fee
        Payment.objects.create(
            customer=cust,
            username=cust.pppoe_username,
            amount=Decimal("1500.00"),
            payment_method="Cash",
            reason="Plan Upgrade to GIMI (includes ₱500 one-time upgrade fee)",
        )
        # Net qualifying paid must be ₱1,000 (fee excluded)
        self.assertEqual(get_customer_qualifying_paid_total(cust), Decimal("1000.00"))
        self.assertEqual(AgentQualificationEvent.objects.filter(customer=cust).count(), 0)

        # Subsequent payment of ₱1,000
        Payment.objects.create(
            customer=cust,
            username=cust.pppoe_username,
            amount=Decimal("1000.00"),
            payment_method="Cash",
        )
        self.assertEqual(get_customer_qualifying_paid_total(cust), Decimal("2000.00"))
        event = AgentQualificationEvent.objects.filter(customer=cust).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.status, "qualified")

    # 5. Cancellation before qualifying never counts; already-qualified stays counted
    def test_cancellation_before_qualifying_never_counts(self):
        # Customer cancelled before qualifying
        cust_cancelled = self._create_customer(
            "Subscriber Cancelled", self.agent_a, "sub_canc", status="closed_not_installed", installation_status="closed_not_installed"
        )
        # Payment on cancelled customer
        Payment.objects.create(
            customer=cust_cancelled, username=cust_cancelled.pppoe_username, amount=Decimal("2000.00"), payment_method="Cash"
        )
        # Must not qualify
        self.assertEqual(AgentQualificationEvent.objects.filter(customer=cust_cancelled).count(), 0)

        # Customer who qualified FIRST, then later cancelled -> stays counted
        cust_valid = self._create_customer("Subscriber Live", self.agent_a, "sub_live")
        Payment.objects.create(
            customer=cust_valid, username=cust_valid.pppoe_username, amount=Decimal("2000.00"), payment_method="Cash"
        )
        event = AgentQualificationEvent.objects.filter(customer=cust_valid).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.status, "qualified")

        # Disconnect / pull out later
        cust_valid.status = "pull out"
        cust_valid.save()
        evaluate_agent_qualification(cust_valid)

        event.refresh_from_db()
        self.assertEqual(event.status, "qualified")

    # 6. Revocation on rollback before payout
    def test_revocation_on_rollback_before_payout(self):
        cust = self._create_customer("Subscriber Rollback", self.agent_a, "sub_rb")

        # Pays ₱2,000 -> qualifies
        Payment.objects.create(
            customer=cust, username=cust.pppoe_username, amount=Decimal("2000.00"), payment_method="Cash"
        )
        event = AgentQualificationEvent.objects.filter(customer=cust).first()
        self.assertEqual(event.status, "qualified")

        # Rollback ₱1,000 (negative payment)
        Payment.objects.create(
            customer=cust,
            username=cust.pppoe_username,
            amount=Decimal("-1000.00"),
            payment_method="Rollback",
            reason="Rollback: Erroneous payment recorded",
        )
        self.assertEqual(get_customer_qualifying_paid_total(cust), Decimal("1000.00"))

        event.refresh_from_db()
        self.assertEqual(event.status, "revoked")
        self.assertIn("rolled back", event.revocation_reason)

        # Customer re-pays ₱1,000 -> re-qualifies
        Payment.objects.create(
            customer=cust, username=cust.pppoe_username, amount=Decimal("1000.00"), payment_method="Cash"
        )
        event.refresh_from_db()
        self.assertEqual(event.status, "qualified")
        self.assertIsNone(event.revocation_reason)

    # 7. Duplicate processing idempotency
    def test_duplicate_processing_is_idempotent(self):
        cust = self._create_customer("Subscriber Idempotent", self.agent_a, "sub_idemp")
        p = Payment.objects.create(
            customer=cust, username=cust.pppoe_username, amount=Decimal("2000.00"), payment_method="Cash"
        )

        # Re-save payment multiple times
        p.save()
        p.save()
        evaluate_agent_qualification(cust)
        evaluate_agent_qualification(cust)

        self.assertEqual(AgentQualificationEvent.objects.filter(customer=cust).count(), 1)

    # 8. Batches of 5 and multiples & carry-over
    def test_batches_of_5_multiples_and_carry_over(self):
        # Create 12 qualified customers for Agent Alpha
        for i in range(12):
            cust = self._create_customer(f"Cust {i+1}", self.agent_a, f"user_batch_{i+1}")
            Payment.objects.create(
                customer=cust, username=cust.pppoe_username, amount=Decimal("2000.00"), payment_method="Cash"
            )

        self.assertEqual(self.agent_a.unpaid_qualified_count, 12)
        summary = get_agent_incentive_summary(self.agent_a)
        self.assertEqual(summary["unpaid_qualified"], 12)
        self.assertEqual(summary["eligible_batches"], 2)  # 2 batches of 5 = 10
        self.assertEqual(summary["claimable_amount"], Decimal("5000.00"))
        self.assertEqual(summary["carry_over"], 2)

        # Create batch of 10
        batch = create_agent_payout_batch(
            agent=self.agent_a,
            batch_size_to_create=10,
            user=self.admin_user,
            notes="Bi-monthly payout",
        )
        self.assertEqual(batch.customer_count, 10)
        self.assertEqual(batch.amount, Decimal("5000.00"))
        self.assertEqual(batch.status, "pending")
        self.assertEqual(batch.customers.count(), 10)

        # 2 remain unpaid (carry over)
        self.assertEqual(self.agent_a.unpaid_qualified_count, 2)
        self.assertEqual(self.agent_a.carry_over_count, 2)

        # Mark paid
        mark_agent_payout_batch_paid(
            batch=batch,
            user=self.staff_permitted,
            reference_no="GCASH-BATCH-9988",
            notes="Transferred via GCash",
        )
        batch.refresh_from_db()
        self.assertEqual(batch.status, "paid")
        self.assertEqual(batch.paid_by, self.staff_permitted)
        self.assertIsNotNone(batch.paid_at)

        # Linked 10 events must be marked paid_out
        self.assertEqual(batch.events.filter(status="paid_out").count(), 10)

    # 9. Permissions & Agent Isolation
    def test_permissions_and_agent_isolation(self):
        # 1. Unpermitted staff cannot access payout list
        self.client.force_login(self.staff_unpermitted)
        resp = self.client.get("/agents/payouts/")
        self.assertEqual(resp.status_code, 302)  # Redirects due to permission denial

        # 2. Permitted staff can access payout list
        self.client.force_login(self.staff_permitted)
        resp = self.client.get("/agents/payouts/")
        self.assertEqual(resp.status_code, 200)

        # 3. Agent isolation: Agent A cannot see Agent B's referrals
        cust_a = self._create_customer("Client of A", self.agent_a, "client_a")
        prospect_a = Prospect.objects.create(
            agent=self.agent_a, full_name="Client of A", converted_customer=cust_a
        )

        cust_b = self._create_customer("Client of B", self.agent_b, "client_b")
        prospect_b = Prospect.objects.create(
            agent=self.agent_b, full_name="Client of B", converted_customer=cust_b
        )

        # Login as Agent A
        self.client.force_login(self.agent_user_a)
        resp_a = self.client.get("/agent-dashboard/")
        self.assertEqual(resp_a.status_code, 200)
        self.assertContains(resp_a, "Client of A")
        self.assertNotContains(resp_a, "Client of B")

        # Login as Agent B
        self.client.force_login(self.agent_user_b)
        resp_b = self.client.get("/agent-dashboard/")
        self.assertEqual(resp_b.status_code, 200)
        self.assertContains(resp_b, "Client of B")
        self.assertNotContains(resp_b, "Client of A")

    # 10. Router sync and non-agent customers never count
    def test_router_sync_and_non_agent_customers_never_count(self):
        # Non-agent customer
        cust_no_agent = Customer.objects.create(
            full_name="Direct Customer",
            pppoe_username="direct_user",
            plan=self.plan,
            status="active",
            installation_status="installed",
            is_test_data=True,
        )
        Payment.objects.create(customer=cust_no_agent, amount=Decimal("2000.00"), payment_method="Cash")
        self.assertEqual(AgentQualificationEvent.objects.filter(customer=cust_no_agent).count(), 0)

        # Router-sync customer with agent
        cust_router_sync = Customer.objects.create(
            full_name="Router Sync Customer",
            pppoe_username="router_sync_user",
            plan=self.plan,
            agent=self.agent_a,
            original_agent=self.agent_a,
            source="router_sync",
            status="active",
            installation_status="installed",
            is_test_data=True,
        )
        Payment.objects.create(customer=cust_router_sync, amount=Decimal("2000.00"), payment_method="Cash")
        self.assertEqual(AgentQualificationEvent.objects.filter(customer=cust_router_sync).count(), 0)
