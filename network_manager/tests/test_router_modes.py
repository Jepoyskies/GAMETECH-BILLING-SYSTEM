from unittest.mock import MagicMock, patch
from django.test import TestCase, override_settings
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI
from network_manager.sync_services import MikrotikAPI as SyncMikrotikAPI
from billing.models import SystemLog


class RouterModeSafetyTests(TestCase):
    """
    Test suite verifying that ROUTER_MODE ('dry_run' | 'read_only' | 'live')
    strictly protects live routers: in 'read_only' and 'dry_run' modes,
    NO write call reaches the router socket.
    """

    def setUp(self):
        self.device = MikrotikDevice.objects.create(
            device_name="Test Router Core",
            ip_address="192.168.88.1",
            api_username="admin",
            api_password="password123",
            api_port=8728,
        )

    @override_settings(ROUTER_MODE="dry_run", ROUTER_DRY_RUN=True)
    def test_dry_run_mode_never_touches_socket(self):
        """In dry_run mode, DryRunConnectionPool is used. Socket library is never invoked."""
        with patch("routeros_api.RouterOsApiPool") as mock_pool:
            api = MikrotikAPI(self.device)
            self.assertTrue(api.is_dry_run)
            self.assertFalse(api.is_read_only)
            # Pool must NOT be instantiated
            mock_pool.assert_not_called()

            # Reads and writes operate on in-memory mock without socket
            success, msg = api.add_pppoe_user(
                name="dryrun_user",
                password="pw",
                profile="default",
            )
            self.assertTrue(success)
            mock_pool.assert_not_called()

    @override_settings(ROUTER_MODE="read_only", ROUTER_DRY_RUN=False)
    def test_read_only_mode_allows_reads_and_blocks_all_writes(self):
        """
        In read_only mode, reads execute against the router API, but EVERY write
        (add, set, remove, call) is intercepted and blocked before touching the socket.
        """
        mock_raw_api = MagicMock()
        mock_raw_secret_res = MagicMock()
        mock_raw_active_res = MagicMock()
        mock_raw_system_res = MagicMock()

        # Configure mocked read responses
        mock_raw_secret_res.get.return_value = [
            {"id": "*1", "name": "alice_test", "profile": "Plan-1500", "comment": "Alice"}
        ]
        mock_raw_active_res.get.return_value = [
            {"id": "*A1", "name": "alice_test", "address": "10.0.0.5"}
        ]
        mock_raw_system_res.get.return_value = [{"uptime": "2d 4h", "cpu-load": "12"}]

        def get_resource_side_effect(path):
            if path == "/ppp/secret":
                return mock_raw_secret_res
            elif path == "/ppp/active":
                return mock_raw_active_res
            elif path == "/system/resource":
                return mock_raw_system_res
            return MagicMock()

        mock_raw_api.get_resource.side_effect = get_resource_side_effect

        with patch("routeros_api.RouterOsApiPool") as mock_pool_cls:
            mock_pool_instance = MagicMock()
            mock_pool_instance.get_api.return_value = mock_raw_api
            mock_pool_cls.return_value = mock_pool_instance

            api = MikrotikAPI(self.device)
            self.assertTrue(api.is_read_only)
            self.assertFalse(api.is_dry_run)

            # 1. READ TEST: Allowed
            secrets = api.get_ppp_secrets()
            self.assertEqual(len(secrets), 1)
            self.assertEqual(secrets[0]["name"], "alice_test")
            mock_raw_secret_res.get.assert_called_once()

            # 2. WRITE TEST: add_pppoe_user
            initial_logs = SystemLog.objects.filter(action="BLOCKED_WRITE").count()
            api.add_pppoe_user(
                name="blocked_user",
                password="pw",
                profile="default",
            )
            # The raw routeros_api resource.add MUST NOT be called!
            mock_raw_secret_res.add.assert_not_called()
            self.assertGreater(
                SystemLog.objects.filter(action="BLOCKED_WRITE").count(),
                initial_logs,
            )

            # 3. WRITE TEST: kick_active_user / remove_active_pppoe_user
            api.kick_active_user("alice_test")
            # raw routeros_api resource.remove MUST NOT be called!
            mock_raw_active_res.remove.assert_not_called()

            # 4. WRITE TEST: Direct resource set / remove
            wrapped_secret = api._get_api().get_resource("/ppp/secret")
            res_set = wrapped_secret.set(id="*1", comment="New Comment")
            self.assertIsNone(res_set)
            mock_raw_secret_res.set.assert_not_called()

            res_remove = wrapped_secret.remove(id="*1")
            self.assertIsNone(res_remove)
            mock_raw_secret_res.remove.assert_not_called()

    @override_settings(ROUTER_MODE="read_only", ROUTER_DRY_RUN=False)
    def test_sync_services_read_only_blocks_writes(self):
        """
        Verify network_manager.sync_services.MikrotikAPI also blocks writes in read_only mode.
        """
        mock_raw_api = MagicMock()
        mock_raw_secret = MagicMock()
        mock_raw_secret.get.return_value = [{"name": "bob", "password": "123", "profile": "p1"}]
        mock_raw_active = MagicMock()
        mock_raw_active.get.return_value = []

        def get_res(path):
            if path == "/ppp/secret":
                return mock_raw_secret
            elif path == "/ppp/active":
                return mock_raw_active
            return MagicMock()

        mock_raw_api.get_resource.side_effect = get_res

        with patch("routeros_api.RouterOsApiPool") as mock_pool_cls:
            mock_pool_instance = MagicMock()
            mock_pool_instance.get_api.return_value = mock_raw_api
            mock_pool_cls.return_value = mock_pool_instance

            sync_api = SyncMikrotikAPI("192.168.88.1", "admin", "pw", 8728)

            # Read works
            res = sync_api.get_all_pppoe_users()
            self.assertTrue(res["success"])
            self.assertEqual(len(res["data"]), 1)

            # Write is blocked
            add_res = sync_api.add_pppoe_user("blocked_bob", "pw", "p1", "Bob")
            self.assertFalse(add_res["success"])
            self.assertIn("Blocked by read_only mode", add_res["error"])
            mock_raw_secret.add.assert_not_called()

            del_res = sync_api.delete_pppoe_user("bob")
            self.assertFalse(del_res["success"])
            self.assertIn("Blocked by read_only mode", del_res["error"])
            mock_raw_secret.remove.assert_not_called()
