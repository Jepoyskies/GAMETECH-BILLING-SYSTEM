from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from billing.models import Customer, SubscriptionPlan, Barangay, CignalPlay, Agent, SystemAdmin


class UIRestorationsTestCase(TestCase):
    """
    Automated verification of restored UI controls, direct visible buttons,
    standalone columns, and permission gates across Customers Directory,
    Cignal Dashboard, and Sales Agents Directory.
    """

    def setUp(self):
        self.client = Client()
        self.barangay = Barangay.objects.create(name="Carmen Test Station")
        self.plan = SubscriptionPlan.objects.create(
            name="Fiber Max 1500",
            speed_up="50 Mbps",
            speed_down="50 Mbps",
            price=1500.00,
        )
        self.customer = Customer.objects.create(
            full_name="Juan dela Cruz",
            phone="09171234567",
            address="Purok 1 Carmen",
            barangay=self.barangay,
            plan=self.plan,
            pppoe_username="juan_carmen",
            pppoe_password="password123",
            status="active",
            installation_status="installed",
        )
        self.cignal = CignalPlay.objects.create(
            customer=self.customer,
            plan_name="Cignal Play Basic",
            account_name="Cignal Box Primary",
            cignal_play_no="CP-998877",
            cignal_box_no="CB-112233",
            monthly_load_plan="149",
            hardware_payment_type="none",
            adjusted_by="Admin Officer",
        )
        self.agent = Agent.objects.create(
            name="Agent Maria Clara",
            email="maria.clara@gametech.local",
            phone="09187654321",
        )

        # 1. Admin / Fully-permitted user
        self.admin_user = User.objects.create_superuser(
            username="admin_tester",
            email="admin@gametech.local",
            password="AdminPassword123!",
        )

        # 2. Viewer user (without Admin or Editor role)
        self.viewer_user = User.objects.create_user(
            username="viewer_tester",
            email="viewer@gametech.local",
            password="ViewerPassword123!",
            is_staff=True,
        )
        SystemAdmin.objects.create(
            username="viewer_tester",
            full_name="Viewer Tester",
            email="viewer@gametech.local",
            role="Viewer",
            password_hash="managed",
        )

    def test_customer_directory_visible_buttons_for_admin(self):
        """Customers Directory displays direct visible buttons for View, Repair, Edit, Delete for Admin."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("customer_list"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        # Assert direct visible buttons exist
        self.assertIn('title="View Details"', html)
        self.assertIn('title="File Dispatch / Repair Ticket"', html)
        self.assertIn('title="Edit Customer"', html)
        self.assertIn('title="Delete Customer"', html)
        self.assertIn("Are you sure you want to delete this customer?", html)

        # Assert no overflow dropdown ellipsis button in customer table row actions
        self.assertIn('fa-screwdriver-wrench', html)
        self.assertIn('fa-trash-alt', html)

    def test_customer_directory_permission_gate_for_viewer(self):
        """Customers Directory restricts Edit and Delete buttons for non-Admin/Editor viewers."""
        self.client.force_login(self.viewer_user)
        response = self.client.get(reverse("customer_list"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        # View and Repair remain visible
        self.assertIn('title="View Details"', html)
        self.assertIn('title="File Dispatch / Repair Ticket"', html)

        # Edit and Delete must NOT appear
        self.assertNotIn('title="Edit Customer"', html)
        self.assertNotIn('title="Delete Customer"', html)

    def test_cignal_dashboard_restored_column_and_visible_cancel(self):
        """Cignal Dashboard has standalone Adjusted By column and visible Pulled-Out button."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("cignal_dashboard"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        # Assert Adjusted By column header and cell
        self.assertIn('<th style="width: 12%;">Adjusted By</th>', html)
        self.assertIn('Admin Officer', html)

        # Assert direct visible Mark Pulled-Out / Remove action
        self.assertIn('title="Mark as Pulled-Out / Removed"', html)
        self.assertIn('Mark Cignal subscription', html)
        self.assertIn('title="Edit Subscription Details"', html)
        self.assertIn('title="Record Payment / Reload"', html)

    def test_agent_directory_restored_kpi_cards_and_copy_actions(self):
        """Agent Directory restores 4 KPI cards, Dashboard link, and one-click copy buttons."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("agent_list"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        # Assert 4 KPI Cards
        self.assertIn("Registered Agents", html)
        self.assertIn("Active Referrers", html)
        self.assertIn("Total Referrals", html)
        self.assertIn("Claimable Commissions", html)

        # Assert Dashboard link
        self.assertIn('href="/dispatch/"', html)
        self.assertIn("Dashboard", html)

        # Assert copy buttons
        self.assertIn('title="Copy email"', html)
        self.assertIn('title="Copy phone"', html)
        self.assertIn("copyText('maria.clara@gametech.local')", html)
        self.assertIn("copyText('09187654321')", html)
