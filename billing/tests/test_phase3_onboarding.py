from django.test import TestCase, Client
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from billing.models import (
    Customer,
    Agent,
    Barangay,
    SubscriptionPlan,
    AccountType,
    Prospect,
    ChecklistConfirmation,
    Notification,
    SystemLog,
)
from dispatch.models import JobTicket


class Phase3OnboardingAndChecklistTests(TestCase):
    def setUp(self):
        # 1. Setup test staff user
        self.staff_user = User.objects.create_user(
            username="test_csr_staff",
            email="staff@gametech.local",
            password="Password123!",
            is_staff=True,
        )
        self.staff_user.role = "CSR"
        self.staff_user.save()

        # Add add_customer and create_customer permissions
        perm_add_cust = Permission.objects.filter(codename="add_customer").first()
        if perm_add_cust:
            self.staff_user.user_permissions.add(perm_add_cust)
        perm_create_cust = Permission.objects.filter(codename="create_customer").first()
        if perm_create_cust:
            self.staff_user.user_permissions.add(perm_create_cust)

        # 2. Setup test agent users & profiles
        self.agent1_user = User.objects.create_user(
            username="test_agent_1",
            email="agent1@gametech.local",
            password="Password123!",
            is_staff=False,
        )
        self.agent1_user.role = "Agent"
        self.agent1_user.save()
        self.agent1 = Agent.objects.create(
            user=self.agent1_user,
            name="Agent Alpha",
            email="agent1@gametech.local",
            phone="09111111111",
            is_test_data=True,
        )

        self.agent2_user = User.objects.create_user(
            username="test_agent_2",
            email="agent2@gametech.local",
            password="Password123!",
            is_staff=False,
        )
        self.agent2_user.role = "Agent"
        self.agent2_user.save()
        self.agent2 = Agent.objects.create(
            user=self.agent2_user,
            name="Agent Bravo",
            email="agent2@gametech.local",
            phone="09222222222",
            is_test_data=True,
        )

        # 3. Setup test master records
        self.barangay = Barangay.objects.create(name="Barangay Carmen", health_status="Excellent")
        self.plan = SubscriptionPlan.objects.create(
            name="Fiber 50 Mbps",
            price=1299.00,
            speed_down="50M",
            speed_up="50M",
        )
        self.account_type = AccountType.objects.create(type_name="Residential")

        self.client = Client()

    def test_direct_post_without_checklist_is_rejected(self):
        """
        Rule 1: Direct POST to /customers/add/ with installation_status='pending'
        WITHOUT all 6 checklist items must be rejected server-side and create no customer.
        """
        self.client.login(username="test_csr_staff", password="Password123!")

        payload = {
            "full_name": "Direct Post Without Checklist",
            "phone": "09123450001",
            "email": "nochecklist@gametech.local",
            "address": "Zone 1, Carmen",
            "barangay_id": self.barangay.id,
            "plan_id": self.plan.id,
            "installation_status": "pending",
            # Deliberately omit checklist checkboxes
        }

        response = self.client.post("/customers/add/", payload)
        # Should re-render form with error message (status 200) rather than redirecting to customer_list (302)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Customer.objects.filter(phone="09123450001").exists())
        self.assertFalse(ChecklistConfirmation.objects.filter(applicant_phone="09123450001").exists())

    def test_valid_checklist_creates_customer_and_unassigned_dispatch_ticket(self):
        """
        Rule 1, 3, 5: A complete checklist with all 6 items creates Customer (Pending Install)
        + ChecklistConfirmation + exactly one unassigned JobTicket in the dispatch queue.
        """
        self.client.login(username="test_csr_staff", password="Password123!")

        payload = {
            "full_name": "Juan Dela Cruz",
            "phone": "09123450002",
            "email": "juan.valid@gametech.local",
            "address": "Zone 2, Carmen",
            "barangay_id": self.barangay.id,
            "plan_id": self.plan.id,
            "installation_status": "pending",
            "installed_at": "2026-10-01",
            # All 6 policy checklist items confirmed
            "checklist_method": "in_person",
            "item_free_install": "true",
            "item_specific_plan": "true",
            "item_no_lockin": "true",
            "item_staggered_lock": "true",
            "item_same_day_repair": "true",
            "item_rebates_24h": "true",
        }

        response = self.client.post("/customers/add/", payload)
        self.assertEqual(response.status_code, 302)

        customer = Customer.objects.filter(phone="09123450002").first()
        self.assertIsNotNone(customer)
        self.assertEqual(customer.status, "pending")
        self.assertEqual(customer.installation_status, "pending")

        # Verify ChecklistConfirmation
        confirmation = ChecklistConfirmation.objects.filter(customer=customer).first()
        self.assertIsNotNone(confirmation)
        self.assertEqual(confirmation.outcome, "agreed")
        self.assertTrue(confirmation.item_free_install)
        self.assertTrue(confirmation.item_specific_plan)
        self.assertTrue(confirmation.item_no_lockin)
        self.assertTrue(confirmation.item_staggered_lock)
        self.assertTrue(confirmation.item_same_day_repair)
        self.assertTrue(confirmation.item_rebates_24h)
        self.assertEqual(confirmation.confirmed_by, self.staff_user)
        self.assertIn("item_free_install", confirmation.policy_snapshot)

        # Verify Unassigned JobTicket in Dispatch Queue (Rule 5 & 6)
        tickets = JobTicket.objects.filter(customer=customer, ticket_type="INSTALLATION")
        self.assertEqual(tickets.count(), 1)
        ticket = tickets.first()
        self.assertEqual(ticket.status, "PENDING")
        self.assertIsNone(ticket.team)
        self.assertEqual(ticket.technicians.count(), 0)

    def test_guarantee_exactly_one_install_ticket_per_customer(self):
        """
        Rule 6: Saving the pending customer multiple times must NOT duplicate installation tickets.
        """
        customer = Customer.objects.create(
            full_name="Idempotency Test User",
            phone="09123450003",
            status="pending",
            installation_status="pending",
            plan=self.plan,
            barangay=self.barangay,
            is_test_data=True,
        )
        # First save triggered signal
        self.assertEqual(JobTicket.objects.filter(customer=customer, ticket_type="INSTALLATION").count(), 1)

        # Trigger save again
        customer.address = "Updated New Address"
        customer.save()
        self.assertEqual(JobTicket.objects.filter(customer=customer, ticket_type="INSTALLATION").count(), 1)

        # Verify ticket details synchronized without adding new ticket
        ticket = JobTicket.objects.filter(customer=customer, ticket_type="INSTALLATION").first()
        self.assertEqual(ticket.address, "Updated New Address")

    def test_manual_override_installed_subscriber_skips_checklist_and_ticket(self):
        """
        Rule 2: "Installed / Existing Subscriber" manual override skips the checklist,
        creates NO installation ticket, requires authorization, and writes a SystemLog entry.
        """
        self.client.login(username="test_csr_staff", password="Password123!")

        payload = {
            "full_name": "Legacy Existing Subscriber",
            "phone": "09123450004",
            "email": "legacy@gametech.local",
            "address": "Zone 3, Carmen",
            "barangay_id": self.barangay.id,
            "plan_id": self.plan.id,
            "installation_status": "installed",
            "status": "expired",
            # No checklist provided
        }

        response = self.client.post("/customers/add/", payload)
        self.assertEqual(response.status_code, 302)

        customer = Customer.objects.filter(phone="09123450004").first()
        self.assertIsNotNone(customer)
        self.assertEqual(customer.installation_status, "installed")

        # Zero ChecklistConfirmation created
        self.assertFalse(ChecklistConfirmation.objects.filter(customer=customer).exists())

        # Zero installation ticket created
        self.assertEqual(JobTicket.objects.filter(customer=customer).count(), 0)

        # SystemLog entry created
        log = SystemLog.objects.filter(table_name="Customer", record_id=str(customer.id), action="MANUAL_OVERRIDE_ADD").first()
        self.assertIsNotNone(log)
        self.assertIn("Manual Override", log.new_data)

    def test_walkin_decline_creates_checklist_confirmation_and_no_customer(self):
        """
        Rule 4: Walk-in declines record ChecklistConfirmation with name, phone, reason,
        and create NO customer in the database.
        """
        self.client.login(username="test_csr_staff", password="Password123!")

        payload = {
            "action": "decline",
            "full_name": "Declined Walkin Applicant",
            "phone": "09123450005",
            "checklist_method": "in_person",
            "decline_reason": "Applicant declined 60-day lock-in terms.",
        }

        response = self.client.post("/customers/add/", payload)
        self.assertEqual(response.status_code, 302)

        # No customer created
        self.assertFalse(Customer.objects.filter(phone="09123450005").exists())

        # ChecklistConfirmation exists without customer or prospect
        confirmation = ChecklistConfirmation.objects.filter(applicant_phone="09123450005").first()
        self.assertIsNotNone(confirmation)
        self.assertIsNone(confirmation.customer)
        self.assertIsNone(confirmation.prospect)
        self.assertEqual(confirmation.outcome, "declined")
        self.assertEqual(confirmation.decline_reason, "Applicant declined 60-day lock-in terms.")
        self.assertEqual(confirmation.applicant_name, "Declined Walkin Applicant")

    def test_agent_referral_decline_updates_prospect_and_shows_in_agent_list(self):
        """
        Rule 4: Declining an agent-referred prospect updates Prospect status to 'declined',
        records decline reason, and creates no customer.
        """
        prospect = Prospect.objects.create(
            agent=self.agent1,
            submitted_by=self.agent1_user,
            full_name="Agent Referred Applicant",
            phone="09123450006",
            barangay=self.barangay,
            plan=self.plan,
            status="submitted",
        )

        self.client.login(username="test_csr_staff", password="Password123!")
        response = self.client.post(f"/prospects/{prospect.id}/decline/", {
            "method": "phone",
            "decline_reason": "Client unreachable after multiple attempts.",
        })
        self.assertEqual(response.status_code, 302)

        prospect.refresh_from_db()
        self.assertEqual(prospect.status, "declined")
        self.assertEqual(prospect.decline_reason, "Client unreachable after multiple attempts.")
        self.assertFalse(Customer.objects.filter(phone="09123450006").exists())

        # Visible in Agent's dashboard
        self.client.login(username="test_agent_1", password="Password123!")
        agent_resp = self.client.get("/agent-dashboard/")
        self.assertEqual(agent_resp.status_code, 200)
        self.assertContains(agent_resp, "Declined")
        self.assertContains(agent_resp, "Client unreachable after multiple attempts.")

    def test_agent_isolation_cannot_access_staff_urls_or_other_agents_referrals(self):
        """
        Rule 7: Agent cannot access staff URLs (redirected) and cannot see other agents' referrals.
        """
        # Create referral for Agent 1 and referral for Agent 2
        p1 = Prospect.objects.create(
            agent=self.agent1,
            submitted_by=self.agent1_user,
            full_name="Agent 1 Unique Lead",
            phone="09123450007",
            barangay=self.barangay,
        )
        p2 = Prospect.objects.create(
            agent=self.agent2,
            submitted_by=self.agent2_user,
            full_name="Agent 2 Private Lead",
            phone="09123450008",
            barangay=self.barangay,
        )

        self.client.login(username="test_agent_1", password="Password123!")

        # Agent 1 attempting to view staff prospect inbox
        resp_inbox = self.client.get("/prospects/")
        self.assertEqual(resp_inbox.status_code, 302)

        # Agent 1 attempting to view staff customer list
        resp_cust = self.client.get("/customers/")
        self.assertEqual(resp_cust.status_code, 302)

        # Agent 1 on their dashboard sees only p1, NOT p2
        resp_dash = self.client.get("/agent-dashboard/")
        self.assertEqual(resp_dash.status_code, 200)
        self.assertContains(resp_dash, "Agent 1 Unique Lead")
        self.assertNotContains(resp_dash, "Agent 2 Private Lead")

    def test_agent_can_edit_prospect_until_staff_opens_it(self):
        """
        Rule 7: Agent can edit a submitted prospect until staff opens/reviews it.
        Once opened_by_staff_at is set, editing is strictly locked.
        """
        prospect = Prospect.objects.create(
            agent=self.agent1,
            submitted_by=self.agent1_user,
            full_name="Editable Lead",
            phone="09123450009",
            barangay=self.barangay,
            status="submitted",
        )

        self.client.login(username="test_agent_1", password="Password123!")

        # 1. Edit allowed before staff opens it
        resp_edit = self.client.post(f"/agent-dashboard/prospects/{prospect.id}/edit/", {
            "full_name": "Editable Lead Updated",
            "phone": "09123450009",
            "barangay": self.barangay.id,
            "address": "Updated Address 123",
        })
        self.assertEqual(resp_edit.status_code, 302)
        prospect.refresh_from_db()
        self.assertEqual(prospect.full_name, "Editable Lead Updated")

        # 2. Staff opens the prospect
        self.client.login(username="test_csr_staff", password="Password123!")
        self.client.get(f"/prospects/{prospect.id}/")
        prospect.refresh_from_db()
        self.assertIsNotNone(prospect.opened_by_staff_at)
        self.assertEqual(prospect.status, "under_review")

        # 3. Agent attempts to edit again -> LOCKED
        self.client.login(username="test_agent_1", password="Password123!")
        resp_edit_blocked = self.client.post(f"/agent-dashboard/prospects/{prospect.id}/edit/", {
            "full_name": "Should Fail",
            "phone": "09123450009",
            "barangay": self.barangay.id,
        })
        self.assertEqual(resp_edit_blocked.status_code, 302)
        prospect.refresh_from_db()
        self.assertNotEqual(prospect.full_name, "Should Fail")
        self.assertEqual(prospect.full_name, "Editable Lead Updated")

    def test_duplicate_detection_and_staff_bell_notification_on_prospect_submit(self):
        """
        Rule 7: Prospect submission flags duplicates against existing customers/prospects
        and generates a high-priority staff bell notification.
        """
        # Create existing customer
        Customer.objects.create(
            full_name="Existing Customer Maria",
            phone="09123450010",
            status="active",
            plan=self.plan,
            barangay=self.barangay,
            is_test_data=True,
        )

        self.client.login(username="test_agent_1", password="Password123!")
        resp_submit = self.client.post("/agent-dashboard/add/", {
            "full_name": "Existing Customer Maria",
            "phone": "09123450010",
            "barangay": self.barangay.id,
            "plan_id": self.plan.id,
        })
        self.assertEqual(resp_submit.status_code, 302)

        prospect = Prospect.objects.filter(phone="09123450010").first()
        self.assertIsNotNone(prospect)
        self.assertTrue(prospect.duplicate_flag)
        self.assertIn("Matches existing subscriber", prospect.duplicate_notes)

        # Staff Bell Notification generated
        notif = Notification.objects.filter(notification_type="prospect", link=f"/prospects/{prospect.id}/").first()
        self.assertIsNotNone(notif)
        self.assertIn("New Referral from Agent Agent Alpha", notif.title)
