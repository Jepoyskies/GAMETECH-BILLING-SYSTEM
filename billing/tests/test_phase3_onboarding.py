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
    ChecklistPolicySetting,
    CustomerAgentHistory,
    Notification,
    SystemLog,
    SystemAdmin,
)
from dispatch.models import JobTicket
from django.core.exceptions import ValidationError


class Phase3OnboardingAndChecklistTests(TestCase):
    def setUp(self):
        # 1. Setup test staff user
        self.staff_user = User.objects.create_user(
            username="test_csr_staff",
            email="staff@gametech.local",
            password="Password123!",
            is_staff=True,
        )
        SystemAdmin.objects.create(
            username="test_csr_staff",
            full_name="Test CSR Staff",
            email="staff@gametech.local",
            role="Admin",
            status="Active",
        )

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


class Phase31RefinementTests(TestCase):
    def setUp(self):
        # 1. Staff users
        self.admin_user = User.objects.create_user(
            username="test_admin_phase31",
            password="Password123!",
            is_staff=True,
            is_superuser=True,
        )

        self.normal_staff = User.objects.create_user(
            username="normal_staff_phase31",
            password="Password123!",
            is_staff=True,
        )
        SystemAdmin.objects.create(
            username="normal_staff_phase31",
            full_name="Normal Staff",
            email="nstaff@gametech.local",
            role="Staff",
            status="Active",
        )
        # Grant standard add_customer and manage_prospects to normal staff
        for perm_name in ["add_customer", "change_customer", "manage_prospects", "create_customer", "run_checklist"]:
            p = Permission.objects.filter(codename=perm_name).first()
            if p:
                self.normal_staff.user_permissions.add(p)

        # Override staff with add_existing_subscriber
        self.override_staff = User.objects.create_user(
            username="override_staff_phase31",
            password="Password123!",
            is_staff=True,
        )
        SystemAdmin.objects.create(
            username="override_staff_phase31",
            full_name="Override Staff",
            email="ostaff@gametech.local",
            role="Admin",
            status="Active",
        )
        for perm_name in ["add_customer", "add_existing_subscriber", "change_customer_agent", "manage_prospects"]:
            p = Permission.objects.filter(codename=perm_name).first()
            if p:
                self.override_staff.user_permissions.add(p)

        # 2. Agent user
        self.agent_user = User.objects.create_user(
            username="agent_privacy_test",
            password="Password123!",
            is_staff=False,
        )
        self.agent = Agent.objects.create(
            user=self.agent_user,
            name="Agent Privacy",
            email="privacy@gametech.local",
            phone="09110000001",
            is_test_data=True,
        )
        self.agent2 = Agent.objects.create(
            name="Agent Secondary",
            email="sec@gametech.local",
            phone="09110000002",
            is_test_data=True,
        )

        # 3. Master records
        self.barangay = Barangay.objects.create(name="Barangay Bugo", health_status="Excellent")
        self.plan = SubscriptionPlan.objects.create(
            name="Fiber Turbo 100",
            price=1500.00,
            speed_down="100M",
            speed_up="100M",
        )
        self.account_type = AccountType.objects.create(type_name="Residential")
        self.client = Client()

    def test_exact_policy_wording_and_dynamic_snapshot(self):
        """
        Item 1: Exact policy wording stored in ChecklistPolicySetting (admin editable).
        Must contain:
        - Free installation
        - Their plan: dynamic plan name and monthly price
        - No lock-in period
        - Staggered payments: 'Not available for 60 days from your first payment' (agent) vs 'Available' (walk-in)
        - Repair within the day
        - Rebates within 24 hours
        MUST NOT contain: '24-month', 'drop cable & ONU', 'weather & fiber availability', 'outage'.
        """
        setting = ChecklistPolicySetting.get_active()
        self.assertEqual(setting.item_free_install_text, "Free installation")
        self.assertEqual(setting.item_no_lockin_text, "No lock-in period")
        self.assertEqual(setting.item_same_day_repair_text, "Repair within the day")
        self.assertEqual(setting.item_rebates_24h_text, "Rebates within 24 hours")

        # Check agent snapshot
        agent_snap = setting.generate_policy_snapshot(plan_name="Turbo 100", price="1500.00", is_agent_referred=True)
        self.assertIn("Turbo 100", agent_snap["item_specific_plan"])
        self.assertIn("₱1500.00/month", agent_snap["item_specific_plan"])
        self.assertIn("Not available for 60 days from your first payment", agent_snap["item_staggered_lock"])

        # Check walkin snapshot
        walkin_snap = setting.generate_policy_snapshot(plan_name="Turbo 100", price="1500.00", is_agent_referred=False)
        self.assertEqual(walkin_snap["item_staggered_lock"], "Staggered payments (3-day, 15-day payments): Available")

        # Assert removed phrases are absent
        forbidden_phrases = ["24-month", "drop cable & ONU", "weather & fiber availability", "outage"]
        full_text = " ".join(str(v) for v in agent_snap.values())
        for phrase in forbidden_phrases:
            self.assertNotIn(phrase, full_text)

    def test_confirmation_method_phone_and_in_person_only(self):
        """
        Item 1: Confirmation methods: in person or phone only (remove chat).
        """
        self.client.login(username="normal_staff_phase31", password="Password123!")

        # Attempt with method='chat' -> Rejected
        payload_chat = {
            "full_name": "Applicant Chat Test",
            "phone": "09180000001",
            "address": "Zone 1 Bugo",
            "barangay_id": self.barangay.id,
            "plan_id": self.plan.id,
            "installation_status": "pending",
            "checklist_free_install": "on",
            "checklist_specific_plan": "on",
            "checklist_no_lockin": "on",
            "checklist_staggered_lock": "on",
            "checklist_same_day_repair": "on",
            "checklist_rebates_24h": "on",
            "checklist_method": "chat",
        }
        resp = self.client.post("/customers/add/", payload_chat)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Customer.objects.filter(phone="09180000001").exists())

        # Valid in_person -> Succeeds
        payload_valid = payload_chat.copy()
        payload_valid["checklist_method"] = "in_person"
        resp_valid = self.client.post("/customers/add/", payload_valid)
        self.assertEqual(resp_valid.status_code, 302)
        cust = Customer.objects.filter(phone="09180000001").first()
        self.assertIsNotNone(cust)
        conf = ChecklistConfirmation.objects.filter(customer=cust).first()
        self.assertIsNotNone(conf)
        self.assertEqual(conf.method, "in_person")

    def test_override_permission_enforcement(self):
        """
        Item 3: Dedicated permission billing.add_existing_subscriber required for
        'Installed / Existing Subscriber' manual override.
        Normal staff without permission is rejected.
        Staff with permission succeeds, writes SystemLog, skips checklist, NO job ticket.
        """
        override_payload = {
            "full_name": "Existing Sub Override Test",
            "phone": "09180000002",
            "address": "Zone 2 Bugo",
            "barangay_id": self.barangay.id,
            "plan_id": self.plan.id,
            "installation_status": "installed",
            "manual_override_type": "existing_subscriber",
            "installed_at": "2026-01-01",
            "expires_at": "2026-12-31",
            "status": "active",
        }

        # 1. Normal staff (lacks add_existing_subscriber)
        self.client.login(username="normal_staff_phase31", password="Password123!")
        resp_blocked = self.client.post("/customers/add/", override_payload)
        self.assertEqual(resp_blocked.status_code, 403)
        self.assertFalse(Customer.objects.filter(phone="09180000002").exists())

        # 2. Override staff (has add_existing_subscriber)
        self.client.login(username="override_staff_phase31", password="Password123!")
        resp_allowed = self.client.post("/customers/add/", override_payload)
        self.assertEqual(resp_allowed.status_code, 302)

        cust = Customer.objects.filter(phone="09180000002").first()
        self.assertIsNotNone(cust)
        self.assertEqual(cust.installation_status, "installed")
        # No checklist confirmation
        self.assertFalse(ChecklistConfirmation.objects.filter(customer=cust).exists())
        # No job ticket created
        self.assertFalse(JobTicket.objects.filter(customer=cust).exists())
        # SystemLog entry exists
        log = SystemLog.objects.filter(table_name="Customer", record_id=str(cust.id), action="MANUAL_OVERRIDE_ADD").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.changed_by, "override_staff_phase31")

    def test_agent_portal_list_privacy(self):
        """
        Item 4: Agent portal referral list shows ONLY: name, status, payment progress, due date.
        NO phone, address, or contact details before or after conversion.
        """
        # Create unconverted prospect
        p_unconverted = Prospect.objects.create(
            agent=self.agent,
            submitted_by=self.agent_user,
            full_name="Secret Applicant Unconverted",
            phone="09998887766",
            address="Confidential Address 999",
            status="submitted",
        )

        # Create converted prospect with customer
        cust = Customer.objects.create(
            full_name="Secret Applicant Converted",
            phone="09995554433",
            address="Private Home 555",
            status="active",
            plan=self.plan,
            barangay=self.barangay,
            is_test_data=True,
        )
        p_converted = Prospect.objects.create(
            agent=self.agent,
            submitted_by=self.agent_user,
            full_name="Secret Applicant Converted",
            phone="09995554433",
            address="Private Home 555",
            status="converted",
            converted_customer=cust,
        )

        self.client.login(username="agent_privacy_test", password="Password123!")
        resp = self.client.get("/agent-dashboard/")
        self.assertEqual(resp.status_code, 200)

        # Should contain names and status
        self.assertContains(resp, "Secret Applicant Unconverted")
        self.assertContains(resp, "Secret Applicant Converted")

        # MUST NOT contain phone numbers or addresses
        self.assertNotContains(resp, "09998887766")
        self.assertNotContains(resp, "Confidential Address 999")
        self.assertNotContains(resp, "09995554433")
        self.assertNotContains(resp, "Private Home 555")

    def test_duplicate_detection_phone_and_name_address(self):
        """
        Item 5: Duplicate detection on phone OR normalized name + address.
        First keeps credit. Second is flagged as duplicate.
        """
        from billing.validators import check_customer_or_prospect_duplicate

        # 1. Existing customer
        Customer.objects.create(
            full_name="Pedro Penduko",
            phone="09171234567",
            address="Purok 4, Carmen",
            status="active",
            plan=self.plan,
            barangay=self.barangay,
            is_test_data=True,
        )

        # Test phone match
        is_dup, reason, obj = check_customer_or_prospect_duplicate(phone="09171234567")
        self.assertTrue(is_dup)
        self.assertIn("Pedro Penduko", reason)

        # Test normalized name + address match (different casing, punctuation, whitespace)
        is_dup_na, reason_na, _ = check_customer_or_prospect_duplicate(
            full_name="  pedro  penduko  ",
            address="purok-4, carmen."
        )
        self.assertTrue(is_dup_na)
        self.assertIn("Pedro Penduko", reason_na)

        # Test agent submission keeps first credit and second is flagged
        self.client.login(username="agent_privacy_test", password="Password123!")
        resp1 = self.client.post("/agent-dashboard/add/", {
            "full_name": "First Unique Applicant",
            "phone": "09179998888",
            "address": "Zone 5",
            "barangay": self.barangay.id,
        })
        self.assertEqual(resp1.status_code, 302)
        p1 = Prospect.objects.filter(phone="09179998888").first()
        self.assertFalse(p1.duplicate_flag)

        # Second submission by agent with same phone
        resp2 = self.client.post("/agent-dashboard/add/", {
            "full_name": "Second Tries To Steal",
            "phone": "09179998888",
            "address": "Zone 5 Different",
            "barangay": self.barangay.id,
        })
        self.assertEqual(resp2.status_code, 302)
        p2 = Prospect.objects.filter(full_name="Second Tries To Steal").first()
        self.assertTrue(p2.duplicate_flag)
        self.assertEqual(p2.duplicate_of, p1)

    def test_shared_model_level_guard_rejects_pending_customer_without_checklist(self):
        """
        Item 6: Customer.save() shared model guard rejects pending customers without checklist.
        """
        cust = Customer(
            full_name="Direct Model Save Attempt",
            phone="09187776655",
            status="pending",
            installation_status="pending",
            plan=self.plan,
            barangay=self.barangay,
            is_test_data=False,
        )
        with self.assertRaises(ValidationError):
            cust.save()

    def test_prospect_single_conversion_and_declined_reopen(self):
        """
        Item 7: A prospect can convert to a customer ONCE (second submit rejected).
        A declined prospect cannot convert unless reopened by staff with reason.
        """
        prospect = Prospect.objects.create(
            agent=self.agent,
            full_name="Single Conversion Prospect",
            phone="09181112233",
            address="Zone 1",
            barangay=self.barangay,
            plan=self.plan,
            status="declined",
            decline_reason="Customer unavailable",
        )

        self.client.login(username="normal_staff_phase31", password="Password123!")

        # 1. Attempt to convert declined prospect without reopening -> Rejected
        payload = {
            "full_name": "Single Conversion Prospect",
            "phone": "09181112233",
            "address": "Zone 1",
            "barangay_id": self.barangay.id,
            "plan_id": self.plan.id,
            "prospect_id": prospect.id,
            "installation_status": "pending",
            "checklist_free_install": "on",
            "checklist_specific_plan": "on",
            "checklist_no_lockin": "on",
            "checklist_staggered_lock": "on",
            "checklist_same_day_repair": "on",
            "checklist_rebates_24h": "on",
            "checklist_method": "in_person",
        }
        resp = self.client.post("/customers/add/", payload)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Customer.objects.filter(phone="09181112233").exists())

        # 2. Staff reopens the prospect with reason
        resp_reopen = self.client.post(f"/prospects/{prospect.id}/reopen/", {
            "reopen_reason": "Customer called back and agreed to install date."
        })
        self.assertEqual(resp_reopen.status_code, 302)
        prospect.refresh_from_db()
        self.assertEqual(prospect.status, "under_review")
        self.assertIsNotNone(prospect.reopened_at)

        # 3. First conversion succeeds
        resp_conv1 = self.client.post("/customers/add/", payload)
        self.assertEqual(resp_conv1.status_code, 302)
        prospect.refresh_from_db()
        self.assertEqual(prospect.status, "converted")
        self.assertIsNotNone(prospect.converted_customer)

        # 4. Second conversion attempt on already-converted prospect -> Rejected
        resp_conv2 = self.client.post("/customers/add/", payload)
        self.assertEqual(resp_conv2.status_code, 200)

    def test_staff_add_customer_on_behalf_of_agent(self):
        """
        Item 8: 'Add Customer to this Agent' creates a Prospect with source='staff_on_behalf'
        that redirects to /customers/add/.
        """
        self.client.login(username="normal_staff_phase31", password="Password123!")
        resp = self.client.get(f"/agents/{self.agent.id}/add-customer-on-behalf/")
        self.assertEqual(resp.status_code, 302)

        prospect = Prospect.objects.filter(agent=self.agent, source="staff_on_behalf").first()
        self.assertIsNotNone(prospect)
        self.assertEqual(prospect.status, "under_review")
        self.assertIn(f"prospect_id={prospect.id}", resp.url)

    def test_reassign_customer_agent_permission_and_reason_enforced(self):
        """
        Item 5: Reassigning an existing customer to a new agent requires
        change_customer_agent permission, a reason, and writes CustomerAgentHistory.
        """
        customer = Customer.objects.create(
            full_name="Agent Reassign Customer",
            phone="09184443322",
            status="active",
            plan=self.plan,
            barangay=self.barangay,
            agent=self.agent,
            is_test_data=True,
        )

        # 1. Normal staff (without change_customer_agent) -> Blocked
        self.client.login(username="normal_staff_phase31", password="Password123!")
        resp_blocked = self.client.post(f"/customers/edit/{customer.id}/", {
            "full_name": customer.full_name,
            "phone": customer.phone,
            "address": customer.address or "",
            "status": "active",
            "agent_id": self.agent2.id,
            "agent_reassign_reason": "Change to agent 2",
        })
        customer.refresh_from_db()
        self.assertEqual(customer.agent, self.agent)

        # 2. Override staff (has change_customer_agent), but omits reason -> Blocked
        self.client.login(username="override_staff_phase31", password="Password123!")
        resp_no_reason = self.client.post(f"/customers/edit/{customer.id}/", {
            "full_name": customer.full_name,
            "phone": customer.phone,
            "address": customer.address or "",
            "status": "active",
            "agent_id": self.agent2.id,
            # No agent_reassign_reason
        })
        customer.refresh_from_db()
        self.assertEqual(customer.agent, self.agent)

        # 3. Override staff with reason -> Succeeds & records CustomerAgentHistory
        resp_success = self.client.post(f"/customers/edit/{customer.id}/", {
            "full_name": customer.full_name,
            "phone": customer.phone,
            "address": customer.address or "",
            "status": "active",
            "agent_id": self.agent2.id,
            "agent_reassign_reason": "Territory reallocation by manager",
        })
        customer.refresh_from_db()
        self.assertEqual(customer.agent, self.agent2)

        history = CustomerAgentHistory.objects.filter(customer=customer).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.from_agent, self.agent)
        self.assertEqual(history.to_agent, self.agent2)
        self.assertEqual(history.reason, "Territory reallocation by manager")
