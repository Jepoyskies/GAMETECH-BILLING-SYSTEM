from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User, Permission
from django.urls import reverse
from billing.models import Customer, SubscriptionPlan, Barangay


class CustomerViewMoreActionsTestCase(TestCase):
    """
    Automated verification of Customer View More Actions dropdown items,
    permission gates, read-only mode annotations, and direct rollback routing.
    """

    def setUp(self):
        self.client = Client()
        self.barangay = Barangay.objects.create(name="Carmen Test Lab")
        self.plan = SubscriptionPlan.objects.create(
            name="Plan 1500",
            speed_up="50 Mbps",
            speed_down="50 Mbps",
            price=1500.00,
        )
        self.customer = Customer.objects.create(
            full_name="Maria Santos",
            phone="09181234567",
            address="Zone 3 Carmen",
            barangay=self.barangay,
            plan=self.plan,
            pppoe_username="maria_test_actions",
            pppoe_password="password123",
            status="active",
            installation_status="installed",
        )

        # 1. Superuser / Fully-permitted staff
        self.admin_user = User.objects.create_superuser(
            username="admin_actions",
            email="admin@gametech.local",
            password="AdminPassword123!",
        )

        # 2. Staff user with Editor role (can view actions) without delete_customer permission
        self.staff_no_delete = User.objects.create_user(
            username="staff_no_delete",
            email="staff@gametech.local",
            password="StaffPassword123!",
            is_staff=True,
        )
        from billing.models import SystemAdmin
        SystemAdmin.objects.create(
            username="staff_no_delete",
            role="Editor",
        )

    def test_all_10_actions_appear_for_permitted_staff(self):
        """Verify that all 10 original actions appear in Customer View for permitted staff/admin."""
        self.client.force_login(self.admin_user)
        url = reverse("view_customer", args=[self.customer.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        expected_items = [
            "Statement of Account",
            "Update Health",
            "Send SMS",
            "Send Email",
            "Rebate",
            "Rollback",
            "Kick Session",
            "Force Suspend",
            "Force Reactivate",
            "Delete",
        ]

        for item in expected_items:
            self.assertIn(
                item,
                html,
                f"Expected More Actions item '{item}' was not found in Customer View HTML.",
            )

        # Assert delete form is present
        delete_url = reverse("delete_customer", args=[self.customer.id])
        self.assertIn(delete_url, html)

    def test_delete_hidden_for_user_without_delete_permission(self):
        """Verify that staff without billing.delete_customer cannot see the Delete item."""
        self.client.force_login(self.staff_no_delete)
        url = reverse("view_customer", args=[self.customer.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        # The other 9 actions must be present
        first_9_items = [
            "Statement of Account",
            "Update Health",
            "Send SMS",
            "Send Email",
            "Rebate",
            "Rollback",
            "Kick Session",
            "Force Suspend",
            "Force Reactivate",
        ]
        for item in first_9_items:
            self.assertIn(
                item,
                html,
                f"Expected item '{item}' missing for staff user without delete perm.",
            )

        # Delete customer form action must NOT be present
        delete_url = reverse("delete_customer", args=[self.customer.id])
        self.assertNotIn(
            delete_url,
            html,
            "Delete action should NOT be visible to staff without delete_customer permission.",
        )

    @override_settings(ROUTER_MODE="read_only")
    def test_read_only_mode_note_rendered_on_router_actions(self):
        """Verify that when ROUTER_MODE=read_only, the Connection section displays Read-Only Mode note."""
        self.client.force_login(self.admin_user)
        url = reverse("view_customer", args=[self.customer.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        self.assertIn("Read-Only Mode", html)

    def test_rollback_direct_link_without_duplicate_popup(self):
        """Verify rollback item links directly to customer_rollback without confirmRollback popup."""
        self.client.force_login(self.admin_user)
        url = reverse("view_customer", args=[self.customer.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")

        rollback_url = reverse("customer_rollback", args=[self.customer.pppoe_username])
        self.assertIn(rollback_url, html)
        self.assertNotIn('onclick="confirmRollback(', html)
