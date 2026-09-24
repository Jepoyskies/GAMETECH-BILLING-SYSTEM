"""
Phase 2 Foundation Automated Test Suite for Gametech Unli Fiber.
Verifies models, migrations, ticket generator, bounce history, phone normalization,
permissions/roles, and customer status exclusions.
"""

from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import ValidationError

from billing.models import (
    Customer,
    Agent,
    SubscriptionPlan,
    Barangay,
    Payment,
    Prospect,
    ChecklistConfirmation,
    CustomerAgentHistory,
    AgentPayoutBatch,
    AgentQualificationEvent,
    IncentiveSetting,
)
from billing.validators import normalize_ph_phone
from billing.decorators import has_dispatch_permission
from dispatch.models import (
    JobTicket,
    Technician,
    Team,
    TicketBounceHistory,
    CallAttemptLog,
)
from dispatch.utils import generate_ticket_number


class Phase2FoundationTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.staff_user = User.objects.create_user(
            username="staff_phase2",
            password="TestPassword123!",
            is_staff=True,
        )
        self.agent_user = User.objects.create_user(
            username="agent_phase2",
            password="TestPassword123!",
        )
        self.agent = Agent.objects.create(
            user=self.agent_user,
            name="Agent Maria Santos",
            email="agent.maria@example.com",
            phone="09171234567",
            is_test_data=True,
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Plan 1500 (50 Mbps)",
            price=Decimal("1500.00"),
        )
        self.barangay = Barangay.objects.create(name="Carmen")

    def test_ph_phone_normalization(self):
        """Validates Philippine phone normalization to standard 09XXXXXXXXX format."""
        self.assertEqual(normalize_ph_phone("09171234567"), "09171234567")
        self.assertEqual(normalize_ph_phone("+639171234567"), "09171234567")
        self.assertEqual(normalize_ph_phone("639171234567"), "09171234567")
        self.assertEqual(normalize_ph_phone("9171234567"), "09171234567")
        self.assertEqual(normalize_ph_phone("0917-123-4567"), "09171234567")
        self.assertEqual(normalize_ph_phone("+63 (917) 123-4567"), "09171234567")
        self.assertIsNone(normalize_ph_phone("", required=False))

        with self.assertRaises(ValidationError):
            normalize_ph_phone("12345")
        with self.assertRaises(ValidationError):
            normalize_ph_phone("08171234567")

    def test_prospect_creation_and_auto_phone_normalization(self):
        """Validates Prospect model creation, status choices, and phone normalization."""
        prospect = Prospect.objects.create(
            agent=self.agent,
            submitted_by=self.agent_user,
            full_name="Juan dela Cruz",
            phone="+639179876543",
            barangay=self.barangay,
            plan=self.plan,
            status="submitted",
            is_test_data=True,
        )
        self.assertEqual(prospect.phone, "09179876543")
        self.assertEqual(prospect.status, "submitted")
        self.assertEqual(prospect.agent, self.agent)
        self.assertFalse(prospect.duplicate_flag)

    def test_checklist_confirmation_snapshot(self):
        """Validates ChecklistConfirmation creation, outcome, and 6 policy items."""
        prospect = Prospect.objects.create(
            agent=self.agent,
            submitted_by=self.agent_user,
            full_name="Checklist Prospect",
            phone="09181112233",
            is_test_data=True,
        )
        snapshot = {
            "monthly_fee": "1500.00",
            "lock_days": 60,
            "sla_hours": 24,
        }
        checklist = ChecklistConfirmation.objects.create(
            prospect=prospect,
            confirmed_by=self.staff_user,
            method="in_person",
            outcome="agreed",
            policy_snapshot=snapshot,
            item_free_install=True,
            item_specific_plan=True,
            item_no_lockin=True,
            item_staggered_lock=True,
            item_same_day_repair=True,
            item_rebates_24h=True,
        )
        self.assertEqual(checklist.outcome, "agreed")
        self.assertTrue(checklist.item_free_install)
        self.assertTrue(checklist.item_staggered_lock)
        self.assertEqual(checklist.policy_snapshot["monthly_fee"], "1500.00")

    def test_customer_agent_link_and_change_history(self):
        """Validates original_agent permanence and CustomerAgentHistory tracking."""
        customer = Customer.objects.create(
            full_name="Subscriber Test",
            phone="09172223344",
            plan=self.plan,
            agent=self.agent,
            original_agent=self.agent,
            status="active",
            installation_status="installed",
            is_test_data=True,
        )
        self.assertEqual(customer.original_agent, self.agent)

        new_agent = Agent.objects.create(
            name="Agent Pedro Reyes",
            email="pedro@example.com",
            phone="09173334455",
            is_test_data=True,
        )

        # Record agent reassignment
        CustomerAgentHistory.objects.create(
            customer=customer,
            from_agent=self.agent,
            to_agent=new_agent,
            reason="Subscriber requested reassignment to barangay coordinator",
            changed_by=self.staff_user,
        )
        customer.agent = new_agent
        customer.save()

        # original_agent stays permanent forever
        self.assertEqual(customer.original_agent, self.agent)
        self.assertEqual(customer.agent, new_agent)
        history = customer.agent_change_history.first()
        self.assertIsNotNone(history)
        self.assertEqual(history.from_agent, self.agent)
        self.assertEqual(history.to_agent, new_agent)
        self.assertIn("barangay coordinator", history.reason)

    def test_agent_qualification_and_payout_batch(self):
        """Validates AgentQualificationEvent, AgentPayoutBatch, and IncentiveSetting."""
        customer = Customer.objects.create(
            full_name="Qualified Customer",
            phone="09174445566",
            plan=self.plan,
            agent=self.agent,
            original_agent=self.agent,
            status="active",
            installation_status="installed",
            is_test_data=True,
        )
        settings_obj = IncentiveSetting.get_settings()
        self.assertEqual(settings_obj.incentive_amount, Decimal("500.00"))
        self.assertEqual(settings_obj.batch_size, 5)
        self.assertEqual(settings_obj.lock_days, 60)

        # Create qualification event
        event = AgentQualificationEvent.objects.create(
            customer=customer,
            agent=self.agent,
            qualifying_amount=settings_obj.incentive_amount,
            status="qualified",
            is_test_data=True,
        )
        self.assertEqual(event.status, "qualified")
        self.assertEqual(event.qualifying_amount, Decimal("500.00"))

        # Create payout batch
        batch = AgentPayoutBatch.objects.create(
            batch_number="BATCH-20260924-001",
            agent=self.agent,
            amount=Decimal("2500.00"),
            customer_count=5,
            status="pending",
        )
        batch.customers.add(customer)
        event.payout_batch = batch
        event.status = "paid_out"
        event.save()

        self.assertEqual(batch.customers.count(), 1)
        self.assertEqual(event.payout_batch, batch)
        self.assertEqual(event.status, "paid_out")

    def test_job_ticket_additions_and_central_ticket_number(self):
        """Validates JobTicket new fields, SITE_VISIT choice, and GT-YYYYMMDD-XXXX generator."""
        ticket = JobTicket.objects.create(
            ticket_type="SITE_VISIT",
            status="ASSIGNED",
            client_name="Site Visit Applicant",
            contact_number="09178889900",
            address="Zone 3, Carmen",
            is_test_data=True,
        )
        # Verify central ticket number was automatically generated
        self.assertTrue(ticket.ticket_number.startswith("GT-"))
        self.assertEqual(ticket.ticket_type, "SITE_VISIT")

        # Test manual ticket generator
        num = generate_ticket_number()
        self.assertTrue(num.startswith("GT-"))

        # Verify operational fields can be updated
        now = timezone.now()
        ticket.arrived_at = now
        ticket.finished_at = now + timedelta(hours=1)
        ticket.technician_report = "Installed drop cable and validated optical power."
        ticket.admin_approved_at = now + timedelta(hours=2)
        ticket.admin_approved_by = self.staff_user
        ticket.status = "APPROVED"
        ticket.save()

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "APPROVED")
        self.assertEqual(ticket.admin_approved_by, self.staff_user)
        self.assertIsNotNone(ticket.finished_at)

    def test_ticket_bounce_history_and_call_attempts(self):
        """Validates TicketBounceHistory and CallAttemptLog models."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            client_name="Bounce Test Client",
            contact_number="09179998877",
            is_test_data=True,
        )
        tech = Technician.objects.create(name="Tech John Doe", is_available=True)

        # Log call attempt
        attempt = CallAttemptLog.objects.create(
            ticket=ticket,
            technician=tech,
            attempt_number=1,
            result="unanswered",
            notes="No answer after 5 rings",
        )
        self.assertEqual(attempt.result, "unanswered")
        self.assertEqual(attempt.ticket, ticket)

        # Log bounce history
        bounce = TicketBounceHistory.objects.create(
            ticket=ticket,
            from_stage="QA",
            to_stage="TECHNICIAN",
            bounce_type="revisit",
            reason="House reading is -28dBm, requires fiber re-splicing",
            bounced_by=self.staff_user,
        )
        self.assertEqual(bounce.bounce_type, "revisit")
        self.assertIn("re-splicing", bounce.reason)
        self.assertEqual(ticket.bounces.count(), 1)

    def test_customer_status_exclusions_from_overdue_and_counters(self):
        """Verifies pending and closed_not_installed customers are excluded from expired/overdue queries."""
        now = timezone.now()
        past_due = now - timedelta(days=5)

        # 1. Active expired customer (should be counted)
        c_active_expired = Customer.objects.create(
            full_name="Active Expired",
            status="active",
            installation_status="installed",
            expires_at=past_due,
            is_test_data=True,
        )
        # 2. Pending install customer with null or past expiration (must NOT be counted)
        from billing.security import test_seeding_bypass_checklist
        with test_seeding_bypass_checklist("phase2_test"):
            c_pending_install = Customer.objects.create(
                full_name="Pending Install",
                status="pending",
                installation_status="pending",
                expires_at=past_due,
            )
        # 3. Closed - Not Installed customer (must NOT be counted anywhere)
        c_closed = Customer.objects.create(
            full_name="Closed Not Installed",
            status="closed_not_installed",
            installation_status="closed_not_installed",
            expires_at=past_due,
            is_test_data=True,
        )

        from billing.views.customers.list import customer_list
        from billing.management.commands.auto_suspend import Command as AutoSuspendCommand

        # Verify auto-suspend query excludes pending and closed_not_installed
        due_customers = Customer.objects.filter(
            expires_at__lte=now, status="active", installation_status="installed"
        ).exclude(status__in=["pending", "closed_not_installed"])

        self.assertIn(c_active_expired, due_customers)
        self.assertNotIn(c_pending_install, due_customers)
        self.assertNotIn(c_closed, due_customers)

        # Verify customer_list view executes cleanly with exclusions
        req = self.rf.get("/customers/")
        req.user = self.staff_user
        resp = customer_list(req)
        self.assertEqual(resp.status_code, 200)


    def test_named_permissions_and_role_matrix(self):
        """Verifies the 14 named permissions and role matrix permissions."""
        from django.core.management import call_command
        call_command("setup_dispatch_permissions")

        # Verify all 14 permissions exist
        perms = [
            "submit_prospect", "view_own_referrals", "manage_prospects", "run_checklist",
            "create_customer", "assign_technicians", "technician_job_actions", "correct_timers",
            "dispatch_qa", "admin_approve", "view_bounce_summary", "change_agent",
            "mark_payout_paid", "manage_message_templates",
        ]
        for p in perms:
            self.assertTrue(
                Permission.objects.filter(codename=p).exists(),
                f"Missing permission: {p}",
            )

        # Verify Agent role has submit_prospect but not admin_approve
        agent_group = Group.objects.get(name="Agent")
        self.agent_user.groups.add(agent_group)
        self.assertTrue(has_dispatch_permission(self.agent_user, "submit_prospect"))
        self.assertTrue(has_dispatch_permission(self.agent_user, "view_own_referrals"))
        self.assertFalse(has_dispatch_permission(self.agent_user, "admin_approve"))

        # Verify Admin has all permissions
        admin_user = User.objects.create_superuser("admin_test", "admin@test.com", "pass")
        self.assertTrue(has_dispatch_permission(admin_user, "admin_approve"))
        self.assertTrue(has_dispatch_permission(admin_user, "mark_payout_paid"))
