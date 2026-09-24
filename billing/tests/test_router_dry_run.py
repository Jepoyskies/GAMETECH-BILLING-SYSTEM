from django.test import TestCase, override_settings
from django.conf import settings
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI
from network_manager.sync_services import MikrotikAPI as SyncMikrotikAPI


class RouterDryRunTestCase(TestCase):
    """
    Validates that ROUTER_DRY_RUN safely intercepts all RouterOS API communications
    and protects physical hardware from receiving commands during test runs.
    """

    def setUp(self):
        self.device = MikrotikDevice.objects.create(
            device_name="Test CCR2004 Lab",
            ip_address="192.168.88.254",
            api_username="admin",
            api_password="test_password",
            api_port=8728,
            health_status="Excellent",
        )

    def test_dry_run_flag_is_active(self):
        """Verify that testing environment automatically defaults ROUTER_DRY_RUN to True."""
        self.assertTrue(getattr(settings, "ROUTER_DRY_RUN", False))

    def test_mikrotik_api_initializes_with_dry_run_pool(self):
        """Verify that MikrotikAPI initializes with the dry run pool and does not open real sockets."""
        api = MikrotikAPI(self.device)
        self.assertTrue(getattr(api, "is_dry_run", False))
        self.assertFalse(api._connection_failed)

    def test_get_system_resources_returns_stubbed_data(self):
        """Verify system resource retrieval returns safe simulated data without network calls."""
        api = MikrotikAPI(self.device)
        resources = api.get_system_resources()
        self.assertIsInstance(resources, dict)
        self.assertIn("board-name", resources)
        self.assertIn("CCR2004", resources["board-name"])

    def test_get_active_pppoe_users_returns_mock_users(self):
        """Verify that active user queries return safe stubbed sessions."""
        api = MikrotikAPI(self.device)
        users = api.get_active_pppoe_users()
        self.assertIsInstance(users, list)
        self.assertTrue(len(users) > 0)
        self.assertEqual(users[0]["name"], "sample_pppoe_user")

    def test_set_pppoe_comment_simulates_success(self):
        """Verify secret comment updates succeed in dry-run store."""
        api = MikrotikAPI(self.device)
        success, msg = api.set_pppoe_comment("sample_pppoe_user", "Dry Run Update")
        self.assertTrue(success)
        self.assertEqual(msg, "Comment updated")

    def test_remove_active_pppoe_user_simulates_success(self):
        """Verify kick/disconnect active user succeeds in dry-run store."""
        api = MikrotikAPI(self.device)
        success, msg = api.remove_active_pppoe_user("sample_pppoe_user")
        self.assertTrue(success)

    def test_sync_mikrotik_api_uses_dry_run_pool(self):
        """Verify sync_services.MikrotikAPI also intercepts connections in dry-run mode."""
        sync_api = SyncMikrotikAPI(
            ip_address="192.168.88.254",
            username="admin",
            password="test_password",
            port=8728,
        )
        pool, api = sync_api._get_api_connection()
        self.assertIsNotNone(pool)
        self.assertIsNotNone(api)
        resource = api.get_resource("/system/resource")
        self.assertTrue(len(resource.get()) > 0)

    @override_settings(ROUTER_MODE="read_only", ROUTER_DRY_RUN=False)
    def test_read_only_auto_suspend_preserves_status_and_marks_blocked(self):
        """Verify auto_suspend does not change customer status to suspended when ROUTER_MODE=read_only."""
        from django.core.management import call_command
        from django.utils import timezone
        from datetime import timedelta
        from billing.models import Customer, SubscriptionPlan, Barangay

        bg, _ = Barangay.objects.get_or_create(name="Lab Barangay")
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="Plan 1000", defaults={"speed_up": "10M", "speed_down": "10M", "price": 1000}
        )
        cust = Customer.objects.create(
            full_name="Past Due Subscriber",
            pppoe_username="past_due_ro",
            status="active",
            installation_status="installed",
            expires_at=timezone.now() - timedelta(days=2),
            mikrotik_device=self.device,
            plan=plan,
            barangay=bg,
        )

        call_command("auto_suspend")
        cust.refresh_from_db()
        # Status MUST NOT be marked suspended in the DB when router write is blocked
        self.assertEqual(cust.status, "active")
        self.assertEqual(cust.sync_status, "Blocked")

    @override_settings(ROUTER_MODE="read_only", ROUTER_DRY_RUN=False)
    def test_read_only_customer_sync_signal_marks_blocked(self):
        """Verify customer post_save sync signal marks sync_status='Blocked' when ROUTER_MODE=read_only."""
        from billing.models import Customer, SubscriptionPlan, Barangay

        bg, _ = Barangay.objects.get_or_create(name="Lab Barangay")
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="Plan 1000", defaults={"speed_up": "10M", "speed_down": "10M", "price": 1000}
        )
        cust = Customer.objects.create(
            full_name="Signal Subscriber",
            pppoe_username="signal_ro",
            status="active",
            installation_status="installed",
            mikrotik_device=self.device,
            plan=plan,
            barangay=bg,
        )
        cust.refresh_from_db()
        self.assertEqual(cust.sync_status, "Blocked")

    @override_settings(ROUTER_MODE="dry_run", ROUTER_DRY_RUN=True)
    def test_dry_run_preserves_existing_test_behavior(self):
        """Verify that dry_run mode continues to simulate successful sync for tests."""
        from billing.models import Customer, SubscriptionPlan, Barangay

        bg, _ = Barangay.objects.get_or_create(name="Lab Barangay")
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="Plan 1000", defaults={"speed_up": "10M", "speed_down": "10M", "price": 1000}
        )
        cust = Customer.objects.create(
            full_name="Dry Run Subscriber",
            pppoe_username="dry_run_cust",
            status="active",
            installation_status="installed",
            mikrotik_device=self.device,
            plan=plan,
            barangay=bg,
        )
        cust.refresh_from_db()
        self.assertEqual(cust.sync_status, "Synced")
