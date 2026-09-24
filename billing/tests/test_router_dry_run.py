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
