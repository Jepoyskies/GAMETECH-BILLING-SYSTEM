from django.test import TestCase, Client
from django.contrib.auth.models import User
from billing.models import SubscriptionPlan, Barangay, Customer, SystemAdmin
from network_manager.models import MikrotikDevice
from dispatch.models import JobTicket


class BaselineWorkflowTestCase(TestCase):
    """
    Baseline test suite verifying DB models, core routes, and auth protection.
    """

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username="admin_test",
            password="adminpassword123!",
            email="admin@gametech.local",
        )
        self.barangay = Barangay.objects.create(name="Carmen")
        self.plan = SubscriptionPlan.objects.create(
            name="GTipid Fiber 1000",
            speed_up="35 Mbps",
            speed_down="35 Mbps",
            price=1000.00,
        )
        self.device = MikrotikDevice.objects.create(
            device_name="Core Router Carmen",
            ip_address="192.168.88.10",
            api_username="admin",
            api_password="pass",
            api_port=8728,
            health_status="Excellent",
        )

    def test_customer_creation_and_query(self):
        """Verify customer record creation and basic properties."""
        customer = Customer.objects.create(
            full_name="Juan Dela Cruz",
            phone="09171234567",
            address="Block 1 Lot 2, Carmen",
            barangay=self.barangay,
            plan=self.plan,
            mikrotik_device=self.device,
            pppoe_username="juan_delacruz",
            pppoe_password="pppoepassword",
            status="active",
        )
        self.assertIsNotNone(customer.id)
        self.assertEqual(customer.plan.name, "GTipid Fiber 1000")
        self.assertTrue(customer.portal_password_hash or customer.portal_password)

    def test_core_views_require_authentication(self):
        """Verify that protected views redirect unauthenticated users to login."""
        endpoints = [
            "/",
            "/customers/",
            "/subscriptions/",
            "/cignal-dashboard/",
            "/dispatch/",
        ]
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(
                response.status_code,
                302,
                f"Endpoint {endpoint} should redirect unauthenticated users",
            )

    def test_core_views_render_for_admin(self):
        """Verify authenticated staff can access the main dashboards."""
        self.client.force_login(self.admin_user)
        endpoints = [
            "/",
            "/customers/",
            "/subscriptions/",
            "/cignal-dashboard/",
            "/dispatch/",
        ]
        for endpoint in endpoints:
            response = self.client.get(endpoint, follow=True)
            self.assertEqual(
                response.status_code,
                200,
                f"Endpoint {endpoint} failed with status {response.status_code}",
            )
