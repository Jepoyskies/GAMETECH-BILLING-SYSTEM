from decimal import Decimal
from unittest.mock import MagicMock, patch
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from billing.models import (
    Customer,
    SubscriptionPlan,
    ChecklistConfirmation,
    ChecklistPolicySetting,
    Payment,
    SystemLog,
)
from network_manager.models import MikrotikDevice
from billing.security import (
    test_seeding_bypass_checklist,
    permission_gated_customer_bypass,
)

User = get_user_model()


class Phase32GuardAndLoopholeTests(TestCase):
    """
    Covers Phase 3.2 requirements:
    C.1: Removal of arbitrary field bypasses (is_test_data, _checklist_verified).
         Enforcement of explicit test context manager and permission-gated admin bypass.
    C.2: Checklist enforced ONLY on create or when first entering pending install;
         existing pending customers can be saved freely by signals, payments, edits, status transitions.
    C.3: Router sync / recovery import permission gating, SystemLog summaries,
         source='router_sync' tagging, and duplicate deduplication.
    """

    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            name="Plan-1500",
            price=Decimal("1500.00"),
            speed_down="50M",
            speed_up="50M",
        )
        self.device = MikrotikDevice.objects.create(
            device_name="Core-Mikrotik",
            ip_address="192.168.88.1",
            api_username="admin",
            api_password="password",
            api_port=8728,
        )
        self.client = Client()

        # Users
        self.admin = User.objects.create_superuser(
            username="super_admin", email="admin@test.com", password="password123"
        )
        self.staff_user = User.objects.create_user(
            username="staff_john",
            email="staff@test.com",
            password="password123",
            is_staff=True,
        )
        self.staff_with_import_perm = User.objects.create_user(
            username="staff_importer",
            email="importer@test.com",
            password="password123",
            is_staff=True,
        )
        import_perm = Permission.objects.get(
            codename="import_router_subscribers"
        )
        self.staff_with_import_perm.user_permissions.add(import_perm)

        # Ensure active policy setting
        ChecklistPolicySetting.get_active()

    def test_record_level_fields_cannot_bypass_checklist_guard(self):
        """C.1: is_test_data and _checklist_verified fields on record CANNOT bypass checklist guard."""
        # 1. Attempt with is_test_data=True
        with self.assertRaises(ValidationError):
            c = Customer(
                full_name="Bypass Hacker",
                pppoe_username="hacker_1",
                installation_status="pending",
                plan=self.plan,
            )
            c.is_test_data = True
            c.save()

        # 2. Attempt with _checklist_verified=True
        with self.assertRaises(ValidationError):
            c = Customer(
                full_name="Bypass Hacker 2",
                pppoe_username="hacker_2",
                installation_status="pending",
                plan=self.plan,
            )
            c._checklist_verified = True
            c.save()

    def test_test_seeding_bypass_works_and_strictly_fails_on_debug_false_prod(self):
        """C.1: Test seeding bypass works in test context, but strictly refuses under DEBUG=False in prod."""
        with test_seeding_bypass_checklist("seed_dispatch_test_data"):
            c = Customer.objects.create(
                full_name="Seeded Customer",
                pppoe_username="seeded_cust_1",
                installation_status="pending",
                plan=self.plan,
            )
            self.assertIsNotNone(c.pk)

        # Simulate production setting (DEBUG=False, sys.argv not testing)
        with patch("billing.security.settings.DEBUG", False), patch("sys.argv", ["gunicorn"]):
            with self.assertRaises(PermissionError):
                with test_seeding_bypass_checklist("seed_in_production"):
                    pass

    def test_permission_gated_admin_bypass_requires_perm_and_writes_system_log(self):
        """C.1: Permission-gated bypass requires billing.bypass_customer_checklist and logs to SystemLog."""
        # User without permission fails
        with self.assertRaises(PermissionError):
            with permission_gated_customer_bypass(self.staff_user, reason="Unauthorized attempt"):
                pass

        # Superuser succeeds and logs
        initial_logs = SystemLog.objects.filter(action="SECURITY_BYPASS").count()
        with permission_gated_customer_bypass(self.admin, reason="Legacy Billing DB Migration Pass"):
            c = Customer.objects.create(
                full_name="Legacy Migrated Customer",
                pppoe_username="legacy_cust_42",
                installation_status="pending",
                plan=self.plan,
            )
            self.assertIsNotNone(c.pk)

        self.assertEqual(
            SystemLog.objects.filter(action="SECURITY_BYPASS").count(),
            initial_logs + 1,
        )
        log = SystemLog.objects.filter(action="SECURITY_BYPASS").latest("changed_at")
        self.assertIn("Legacy Billing DB Migration Pass", log.new_data)
        self.assertIn("super_admin", log.changed_by)

    def test_existing_pending_customer_saves_freely_without_validation_error(self):
        """
        C.2: Guard triggers ONLY on creation or entering pending.
        Existing pending customer can be saved by edits, payments, dispatch signals, status transitions.
        """
        # Create an existing pending customer legitimately with checklist
        with test_seeding_bypass_checklist("setup"):
            cust = Customer.objects.create(
                full_name="Pending Juan",
                pppoe_username="juan_pending_test",
                installation_status="pending",
                status="pending",
                plan=self.plan,
                phone="09171234567",
            )

        # 1. Edit details and save -> Must succeed without ValidationError
        cust.phone = "09179998888"
        cust.address = "Block 1 Lot 2 Camella Homes"
        cust.save()
        cust.refresh_from_db()
        self.assertEqual(cust.phone, "09179998888")

        # 2. Payment signal / update -> Must succeed
        payment = Payment.objects.create(
            customer=cust,
            username=cust.pppoe_username,
            amount=Decimal("1500.00"),
            payment_method="cash",
            payment_date_received=timezone.now(),
        )
        self.assertIsNotNone(payment.pk)

        # 3. Status transition from pending -> active / installed -> Must succeed
        cust.installation_status = "installed"
        cust.status = "active"
        cust.installed_at = timezone.now()
        cust.save()
        cust.refresh_from_db()
        self.assertEqual(cust.installation_status, "installed")
        self.assertEqual(cust.status, "active")

    def test_router_sync_path4_sync_device_users_permission_source_and_deduplication(self):
        """
        C.3 (Path 4): sync_device_users requires import_router_subscribers permission,
        sets source='router_sync', prevents duplicates by pppoe_username, and writes SystemLog.
        """
        # Create an existing customer to test duplicate rejection
        with test_seeding_bypass_checklist("setup"):
            Customer.objects.create(
                full_name="Existing User",
                pppoe_username="existing_user",
                status="active",
                installation_status="installed",
            )

        mock_secrets = [
            {"name": "existing_user", "password": "p1", "profile": "Plan-1500", "comment": "Existing User"},
            {"name": "new_router_user", "password": "p2", "profile": "Plan-1500", "comment": "Brand New User"},
        ]

        # 1. Unauthorized attempt (staff_user lacks permission)
        self.client.force_login(self.staff_user)
        sync_users_url = reverse('sync_device_users', args=[self.device.id])
        resp = self.client.post(sync_users_url)
        self.assertEqual(resp.status_code, 403)

        # 2. Authorized attempt (staff_with_import_perm)
        self.client.force_login(self.staff_with_import_perm)
        with patch("network_manager.services.MikrotikAPI.get_ppp_secrets", return_value=mock_secrets):
            resp = self.client.post(sync_users_url)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "success")

            # Verify: new customer created with source='router_sync'
            new_c = Customer.objects.get(pppoe_username="new_router_user")
            self.assertEqual(new_c.source, "router_sync")
            self.assertEqual(new_c.installation_status, "installed")

            # Verify: duplicate existing_user was not duplicated
            self.assertEqual(Customer.objects.filter(pppoe_username="existing_user").count(), 1)

            # Verify: summary SystemLog created
            summary_log = SystemLog.objects.filter(
                action="ROUTER_SYNC_IMPORT", target_name=self.device.device_name
            ).latest("changed_at")
            self.assertIn("1 imported, 1 skipped", summary_log.new_data)

    def test_router_sync_path5_bulk_import_permission_source_and_deduplication(self):
        """
        C.3 (Path 5): bulk_import action requires import_router_subscribers permission,
        sets source='router_sync', prevents duplicates, and writes SystemLog.
        """
        with test_seeding_bypass_checklist("setup"):
            Customer.objects.create(
                full_name="Duplicate User",
                pppoe_username="dup_user",
                status="active",
                installation_status="installed",
            )

        mock_users_data = {
            "success": True,
            "data": [
                {"name": "dup_user", "password": "pw", "comment": "Duplicate User"},
                {"name": "fresh_user", "password": "pw", "comment": "Fresh User"},
            ],
        }

        bulk_url = reverse('sync_bulk_action', args=[self.device.id])

        # 1. Unauthorized user fails
        self.client.force_login(self.staff_user)
        resp = self.client.post(
            bulk_url,
            {"action": "bulk_import", "usernames": ["dup_user", "fresh_user"]},
        )
        self.assertEqual(resp.status_code, 302)
        # Should redirect back with error message and NOT import
        self.assertFalse(Customer.objects.filter(pppoe_username="fresh_user").exists())

        # 2. Authorized user succeeds
        self.client.force_login(self.staff_with_import_perm)
        with patch("network_manager.sync_services.MikrotikAPI.get_all_pppoe_users", return_value=mock_users_data):
            resp = self.client.post(
                bulk_url,
                {"action": "bulk_import", "usernames": ["dup_user", "fresh_user"]},
            )
            self.assertEqual(resp.status_code, 302)

            # Verify fresh_user imported with source='router_sync'
            fresh = Customer.objects.get(pppoe_username="fresh_user")
            self.assertEqual(fresh.source, "router_sync")
            self.assertEqual(fresh.installation_status, "installed")

            # Verify dup_user was not duplicated
            self.assertEqual(Customer.objects.filter(pppoe_username="dup_user").count(), 1)

            # Verify SystemLog
            summary_log = SystemLog.objects.filter(
                action="ROUTER_SYNC_IMPORT", target_name=self.device.device_name
            ).latest("changed_at")
            self.assertIn("1 imported, 1 skipped", summary_log.new_data)

    def test_router_recovery_path6_recover_from_mikrotik_command(self):
        """
        C.3 (Path 6): recover_from_mikrotik command sets source='router_sync',
        prevents duplicates by pppoe_username, and writes summary SystemLog.
        """
        from io import StringIO
        from django.core.management import call_command

        with test_seeding_bypass_checklist("setup"):
            Customer.objects.create(
                full_name="Pre Existing",
                pppoe_username="pre_existing",
                status="active",
                installation_status="installed",
            )

        mock_recovery_data = {
            "success": True,
            "data": [
                {"name": "pre_existing", "password": "new_password", "profile": "Plan-1500", "caller-id": ""},
                {"name": "recovered_sub", "password": "pass", "profile": "Plan-1500", "caller-id": "AA:BB:CC:DD:EE:FF"},
            ],
        }

        with patch("network_manager.sync_services.MikrotikAPI.get_all_pppoe_users", return_value=mock_recovery_data):
            out = StringIO()
            call_command("recover_from_mikrotik", stdout=out)
            output = out.getvalue()
            self.assertIn("Emergency Recovery Complete", output)

            # Verify new record
            recovered = Customer.objects.get(pppoe_username="recovered_sub")
            self.assertEqual(recovered.source, "router_sync")
            self.assertEqual(recovered.installation_status, "installed")

            # Verify duplicate was updated, not duplicated
            self.assertEqual(Customer.objects.filter(pppoe_username="pre_existing").count(), 1)
            pre = Customer.objects.get(pppoe_username="pre_existing")
            self.assertEqual(pre.pppoe_password, "new_password")

            # Verify SystemLog
            summary_log = SystemLog.objects.filter(
                action="ROUTER_RECOVERY_IMPORT", target_name=self.device.device_name
            ).latest("changed_at")
            self.assertIn("1 created, 1 updated, 0 skipped", summary_log.new_data)
