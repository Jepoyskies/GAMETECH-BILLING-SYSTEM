from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from billing.models import Customer, SubscriptionPlan, Barangay, SystemLog, SmsLog
from billing.validators import (
    validate_password_policy,
    generate_temp_password,
    is_temp_password_expired,
)
from billing.security import (
    is_account_or_ip_locked,
    record_login_failure,
    clear_login_failures,
    is_ip_rate_limited,
)


class Phase1SecurityTestCase(TestCase):
    """
    Automated verification of Phase 1: Security Hardening & Logins
    """

    def setUp(self):
        self.client = Client()
        self.barangay = Barangay.objects.create(name="Carmen Security Lab")
        self.plan = SubscriptionPlan.objects.create(
            name="Plan 1000",
            speed_up="35 Mbps",
            speed_down="35 Mbps",
            price=1000.00,
        )
        self.customer = Customer.objects.create(
            full_name="Juan Dela Cruz",
            phone="09171234567",
            address="Block 1 Lot 2",
            barangay=self.barangay,
            plan=self.plan,
            pppoe_username="juan_sec",
            pppoe_password="pppoe_secret_password",
            status="active",
        )

    def test_portal_password_hashing(self):
        """Verify that portal passwords are stored as PBKDF2 hashes and plaintext is blanked."""
        raw_pw = "SecurePass123!@"
        self.customer.set_portal_password(raw_pw)
        self.customer.save()

        # Reload from DB
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.portal_password)
        self.assertIsNotNone(self.customer.portal_password_hash)
        self.assertTrue(self.customer.portal_password_hash.startswith("pbkdf2_") or "sha256" in self.customer.portal_password_hash)
        self.assertTrue(self.customer.check_portal_password(raw_pw))
        self.assertFalse(self.customer.check_portal_password("WrongPassword123!@"))

    def test_legacy_plaintext_migration_and_fallback(self):
        """Verify that plaintext fallback is removed (unhashed records return False until hashed on save)."""
        # Simulate unmigrated legacy record
        Customer.objects.filter(id=self.customer.id).update(
            portal_password="legacyplaintext1",
            portal_password_hash=None,
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.portal_password, "legacyplaintext1")
        # Plaintext fallback is removed: unhashed record must return False
        self.assertFalse(self.customer.check_portal_password("legacyplaintext1"))

        # Trigger save to auto-hash and blank legacy plaintext
        self.customer.save()
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.portal_password)
        self.assertIsNotNone(self.customer.portal_password_hash)
        self.assertTrue(self.customer.check_portal_password("legacyplaintext1"))

    def test_global_password_policy_enforcement(self):
        """Verify strict password rules across length, character diversity, and common words."""
        # 1. Under 10 chars
        with self.assertRaises(ValidationError):
            validate_password_policy("Short1!")

        # 2. No letter
        with self.assertRaises(ValidationError):
            validate_password_policy("1234567890!@#")

        # 3. No number
        with self.assertRaises(ValidationError):
            validate_password_policy("NoNumbersHere!@#")

        # 4. No special character
        with self.assertRaises(ValidationError):
            validate_password_policy("NoSpecialChars1234")

        # 5. Common password
        with self.assertRaises(ValidationError):
            validate_password_policy("password123")

        # 6. Matches or contains username or phone
        with self.assertRaises(ValidationError):
            validate_password_policy("Juan_sec123!@", user_or_customer=self.customer)
        with self.assertRaises(ValidationError):
            validate_password_policy("09171234567!Aa", user_or_customer=self.customer)

        # 7. Valid password passes
        try:
            validate_password_policy("GametechPass2026#$", user_or_customer=self.customer)
        except ValidationError:
            self.fail("Valid strong password was unexpectedly rejected.")

    def test_temp_password_generator_and_expiration(self):
        """Verify temporary password length, look-alike character avoidance, and 7-day expiration."""
        temp_pw = generate_temp_password(10)
        self.assertEqual(len(temp_pw), 10)
        # Verify no look-alike characters (0, O, 1, l, I)
        for forbidden in ["0", "O", "1", "l", "I"]:
            self.assertNotIn(forbidden, temp_pw)

        # Expiration logic
        now = timezone.now()
        fresh_time = now - timedelta(days=2)
        expired_time = now - timedelta(days=8)

        self.assertFalse(is_temp_password_expired(fresh_time, max_days=7))
        self.assertTrue(is_temp_password_expired(expired_time, max_days=7))

    def test_portal_login_rejects_fullname_and_pppoe_password(self):
        """Verify that full-name login and PPPoE password logins are rejected."""
        self.customer.set_portal_password("ValidPortal10!#")
        self.customer.save()

        # Attempt 1: Full name with portal password (FORBIDDEN)
        resp1 = self.client.post("/login/", {
            "username": self.customer.full_name,
            "password": "ValidPortal10!#",
        })
        self.assertEqual(resp1.status_code, 200)  # Re-renders login with error
        self.assertNotIn("customer_id", self.client.session)

        # Attempt 2: Username with PPPoE password (FORBIDDEN)
        resp2 = self.client.post("/login/", {
            "username": self.customer.pppoe_username,
            "password": self.customer.pppoe_password,
        })
        self.assertEqual(resp2.status_code, 200)
        self.assertNotIn("customer_id", self.client.session)

        # Attempt 3: Username with Portal Password (ALLOWED)
        resp3 = self.client.post("/login/", {
            "username": self.customer.pppoe_username,
            "password": "ValidPortal10!#",
        })
        self.assertIn(resp3.status_code, [302, 200])
        self.assertEqual(self.client.session.get("customer_id"), self.customer.id)

    def test_portal_login_via_phone_number(self):
        """Verify subscriber can log in using mobile number + portal password."""
        self.customer.set_portal_password("ValidPortal10!#")
        self.customer.save()

        resp = self.client.post("/login/", {
            "username": self.customer.phone,
            "password": "ValidPortal10!#",
        })
        self.assertIn(resp.status_code, [302, 200])
        self.assertEqual(self.client.session.get("customer_id"), self.customer.id)

    def test_brute_force_lockout_after_five_attempts(self):
        """Verify that 5 failed attempts locks that account + IP for 15 minutes."""
        identifier = "target_subscriber"
        test_ip = "192.168.1.100"

        clear_login_failures(identifier, test_ip)
        self.assertFalse(is_account_or_ip_locked(identifier, test_ip)[0])

        for attempt in range(1, 5):
            is_locked, count, _ = record_login_failure(identifier, test_ip, max_attempts=5, lock_duration=900)
            self.assertFalse(is_locked)
            self.assertEqual(count, attempt)

        # 5th attempt locks
        is_locked, count, remaining = record_login_failure(identifier, test_ip, max_attempts=5, lock_duration=900)
        self.assertTrue(is_locked)
        self.assertEqual(count, 5)
        self.assertTrue(remaining > 800)

        # Verify query returns locked
        locked, rem = is_account_or_ip_locked(identifier, test_ip)
        self.assertTrue(locked)
        self.assertTrue(rem > 800)

        # Cleanup
        clear_login_failures(identifier, test_ip)
        self.assertFalse(is_account_or_ip_locked(identifier, test_ip)[0])

    def test_ip_rate_limiting(self):
        """Verify that IP rate limiting throttles requests beyond limit."""
        test_ip = "192.168.10.50"
        for _ in range(15):
            is_limited, _ = is_ip_rate_limited(test_ip, endpoint_name="test_endpoint", limit=15, window=60)
            self.assertFalse(is_limited)

        # 16th attempt should be rate limited
        is_limited, retry_after = is_ip_rate_limited(test_ip, endpoint_name="test_endpoint", limit=15, window=60)
        self.assertTrue(is_limited)
        self.assertTrue(retry_after > 0)

    def test_auth_password_validators_django_admin(self):
        """Verify that AUTH_PASSWORD_VALIDATORS enforces 10+ chars, letter, number, special char, common check, and username match."""
        from django.contrib.auth.password_validation import validate_password

        admin_user = User.objects.create_superuser("admin_hero", "admin@example.com", "TempPassword123!")

        # 1. Too short (< 10 chars)
        with self.assertRaises(ValidationError):
            validate_password("Short1!", user=admin_user)

        # 2. No letter
        with self.assertRaises(ValidationError):
            validate_password("1234567890!@#", user=admin_user)

        # 3. No number
        with self.assertRaises(ValidationError):
            validate_password("NoNumbersHere!@#", user=admin_user)

        # 4. No special char
        with self.assertRaises(ValidationError):
            validate_password("NoSpecialChars123", user=admin_user)

        # 5. Common weak password
        with self.assertRaises(ValidationError):
            validate_password("password123", user=admin_user)

        # 6. Contains username
        with self.assertRaises(ValidationError):
            validate_password("admin_hero!999", user=admin_user)

        # 7. Strong compliant password succeeds
        validate_password("StrongP@ssw0rd2026", user=admin_user)

    def test_staff_and_technician_creation_password_policy(self):
        """Verify that add_staff rejects weak passwords and accepts strong compliant passwords for Staff and Technician."""
        from billing.models import StaffRole, SystemAdmin

        admin_user = User.objects.create_superuser("sec_super", "sec@example.com", "SuperSec123!")
        self.client.force_login(admin_user)

        StaffRole.objects.get_or_create(name="CSR")
        StaffRole.objects.get_or_create(name="Technician")

        # 1. Staff creation with weak password fails
        resp_weak = self.client.post("/staff/add/", {
            "username": "csr_john",
            "full_name": "John CSR",
            "email": "csr@example.com",
            "role": "CSR",
            "status": "Active",
            "password": "weak",
        })
        self.assertFalse(User.objects.filter(username="csr_john").exists())

        # 2. Staff creation with valid password succeeds
        resp_valid = self.client.post("/staff/add/", {
            "username": "csr_john",
            "full_name": "John CSR",
            "email": "csr@example.com",
            "role": "CSR",
            "status": "Active",
            "password": "ValidCSR#Pass2026",
        })
        self.assertTrue(User.objects.filter(username="csr_john").exists())
        self.assertTrue(SystemAdmin.objects.filter(username="csr_john").exists())

        # 3. Technician creation with weak password fails
        resp_tech_weak = self.client.post("/staff/add/", {
            "username": "tech_bob",
            "full_name": "Bob Tech",
            "email": "tech@example.com",
            "role": "Technician",
            "status": "Active",
            "password": "tech_bob123",  # lacks special char and contains username
        })
        self.assertFalse(User.objects.filter(username="tech_bob").exists())

        # 4. Technician creation with valid password succeeds
        resp_tech_valid = self.client.post("/staff/add/", {
            "username": "tech_bob",
            "full_name": "Bob Tech",
            "email": "tech@example.com",
            "role": "Technician",
            "status": "Active",
            "password": "ValidTech#Pass2026",
        })
        self.assertTrue(User.objects.filter(username="tech_bob").exists())

    def test_admin_password_change_policy(self):
        """Verify that edit_staff rejects weak password updates for admin users."""
        from billing.models import StaffRole, SystemAdmin

        super_user = User.objects.create_superuser("master_admin", "master@example.com", "MasterSec#2026")
        self.client.force_login(super_user)

        admin_role, _ = StaffRole.objects.get_or_create(name="Admin")
        staff_admin = SystemAdmin.objects.create(
            username="target_admin",
            full_name="Target Admin",
            email="target@example.com",
            role="Admin",
            status="Active",
        )
        target_u = User.objects.create_user("target_admin", "target@example.com", "InitialSec#2026")

        # Edit with weak password fails
        self.client.post(f"/staff/edit/{staff_admin.pk}/", {
            "username": "target_admin",
            "full_name": "Target Admin",
            "email": "target@example.com",
            "role": "Admin",
            "status": "Active",
            "password": "weakpassword",
        })
        target_u.refresh_from_db()
        self.assertTrue(target_u.check_password("InitialSec#2026"))

        # Edit with compliant password succeeds
        self.client.post(f"/staff/edit/{staff_admin.pk}/", {
            "username": "target_admin",
            "full_name": "Target Admin",
            "email": "target@example.com",
            "role": "Admin",
            "status": "Active",
            "password": "NewStrongAdmin#2026",
        })
        target_u.refresh_from_db()
        self.assertTrue(target_u.check_password("NewStrongAdmin#2026"))
