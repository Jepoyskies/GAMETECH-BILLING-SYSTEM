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
        """Verify that legacy plaintext passwords fallback cleanly and hash on save."""
        # Simulate unmigrated legacy record
        Customer.objects.filter(id=self.customer.id).update(
            portal_password="legacyplaintext1",
            portal_password_hash=None,
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.portal_password, "legacyplaintext1")
        self.assertTrue(self.customer.check_portal_password("legacyplaintext1"))

        # Trigger save
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
