from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from billing.models import Customer, SubscriptionPlan, Barangay, SystemLog, SmsLog
from billing.security import clear_login_failures


class CustomerPortalSecurityTestCase(TestCase):
    """
    Automated security tests for customer_portal authentication, lockout,
    password policy enforcement, temporary password expiration, and
    credential masking during reset/resend.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.barangay = Barangay.objects.create(name="Macasandig Lab")
        self.plan = SubscriptionPlan.objects.create(
            name="Plan 1500",
            speed_up="50 Mbps",
            speed_down="50 Mbps",
            price=1500.00,
        )
        self.customer = Customer.objects.create(
            full_name="Maria Santos",
            phone="09179876543",
            address="Purok 4",
            barangay=self.barangay,
            plan=self.plan,
            pppoe_username="maria_santos",
            pppoe_password="pppoe_secret_password",
            status="active",
        )
        self.compliant_password = "Str0ng#P@ssw0rd99!"
        self.customer.set_portal_password(self.compliant_password)
        self.customer.must_change_password = False
        self.customer.save()

        self.staff_user = User.objects.create_user(
            username="staff_admin",
            password="Compliant#Staff123",
            is_staff=True,
        )

    def tearDown(self):
        cache.clear()

    def test_login_by_phone(self):
        """Customer can authenticate using registered mobile number instead of PPPoE username."""
        # 1. Login using local 11-digit mobile format
        response = self.client.post(reverse('customer_portal:portal_login'), {
            'username': '09179876543',
            'password': self.compliant_password,
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('customer_portal:portal_dashboard'))
        self.assertEqual(self.client.session.get('customer_id'), self.customer.id)

        # Logout and test with +63 format
        self.client.logout()
        cache.clear()

        response2 = self.client.post(reverse('customer_portal:portal_login'), {
            'username': '+639179876543',
            'password': self.compliant_password,
        })
        self.assertEqual(response2.status_code, 302)
        self.assertRedirects(response2, reverse('customer_portal:portal_dashboard'))

    def test_login_lockout_after_failed_attempts(self):
        """5 consecutive failed login attempts trigger a 15-minute account/IP lockout."""
        phone = self.customer.phone
        # Submit 5 incorrect password attempts
        for attempt in range(1, 6):
            resp = self.client.post(reverse('customer_portal:portal_login'), {
                'username': phone,
                'password': 'WrongPassword123!',
            })
            self.assertEqual(resp.status_code, 200)

        # 6th attempt should be blocked by lockout immediately even with correct password
        blocked_resp = self.client.post(reverse('customer_portal:portal_login'), {
            'username': phone,
            'password': self.compliant_password,
        })
        self.assertEqual(blocked_resp.status_code, 200)
        messages_text = [m.message for m in blocked_resp.context['messages']]
        self.assertTrue(
            any("locked" in msg.lower() or "too many failed" in msg.lower() for msg in messages_text),
            f"Expected lockout message in {messages_text}",
        )
        self.assertIsNone(self.client.session.get('customer_id'))

    def test_forced_password_change_with_policy(self):
        """If must_change_password=True, login redirects to forced change page and enforces policy."""
        self.customer.must_change_password = True
        self.customer.save(update_fields=['must_change_password'])

        # Login successfully
        resp = self.client.post(reverse('customer_portal:portal_login'), {
            'username': self.customer.pppoe_username,
            'password': self.compliant_password,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('customer_portal:force_change_password'))

        # Attempt to set a weak/common password
        weak_resp = self.client.post(reverse('customer_portal:force_change_password'), {
            'new_password': 'password123',
            'confirm_password': 'password123',
        })
        self.assertEqual(weak_resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.must_change_password)

        # Attempt to set password containing username
        user_resp = self.client.post(reverse('customer_portal:force_change_password'), {
            'new_password': 'maria_santos123!A',
            'confirm_password': 'maria_santos123!A',
        })
        self.assertEqual(user_resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.must_change_password)

        # Set a fully compliant new password
        new_valid_pw = "N3w#Secur3P@ssw0rd!"
        good_resp = self.client.post(reverse('customer_portal:force_change_password'), {
            'new_password': new_valid_pw,
            'confirm_password': new_valid_pw,
        })
        self.assertEqual(good_resp.status_code, 302)
        self.assertRedirects(good_resp, reverse('customer_portal:portal_dashboard'))

        # Verify customer state updated in DB
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.must_change_password)
        self.assertIsNone(self.customer.temp_password_created_at)
        self.assertIsNone(self.customer.portal_password)
        self.assertTrue(self.customer.check_portal_password(new_valid_pw))

    def test_temporary_password_expiry(self):
        """Temporary passwords older than 7 days are expired and cannot be used to log in."""
        self.customer.temp_password_created_at = timezone.now() - timedelta(days=8)
        self.customer.must_change_password = True
        self.customer.save(update_fields=['temp_password_created_at', 'must_change_password'])

        resp = self.client.post(reverse('customer_portal:portal_login'), {
            'username': self.customer.pppoe_username,
            'password': self.compliant_password,
        })
        self.assertEqual(resp.status_code, 200)
        messages_text = [m.message for m in resp.context['messages']]
        self.assertTrue(
            any("expired" in msg.lower() for msg in messages_text),
            f"Expected expired temp password error in {messages_text}",
        )
        self.assertIsNone(self.client.session.get('customer_id'))

    def test_reset_and_resend_never_logs_plaintext(self):
        """Staff resetting portal password dispatches SMS with masked body and never writes plaintext to logs."""
        self.client.force_login(self.staff_user)

        reset_resp = self.client.post(
            reverse('reset_customer_portal_password', args=[self.customer.id]),
            follow=True,
        )
        self.assertEqual(reset_resp.status_code, 200)

        # Verify customer credentials state
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.must_change_password)
        self.assertIsNotNone(self.customer.temp_password_created_at)
        self.assertIsNone(self.customer.portal_password)

        # Retrieve generated temp password from session (only place temporary password resides during display)
        temp_data = self.client.session.get("customer_temp_password_display")
        self.assertIsNotNone(temp_data)
        generated_pw = temp_data.get("temp_password")
        self.assertTrue(bool(generated_pw))

        # Check SmsLog: must contain [REDACTED] and NEVER the generated plain password
        sms = SmsLog.objects.filter(phone=self.customer.phone).order_by('-id').first()
        self.assertIsNotNone(sms)
        self.assertIn("[REDACTED]", sms.message)
        self.assertNotIn(generated_pw, sms.message)

        # Check SystemLog: must NEVER contain the generated plain password
        logs = SystemLog.objects.filter(record_id=str(self.customer.id), action="RESET_PORTAL_PASSWORD")
        self.assertTrue(logs.exists())
        for log in logs:
            self.assertNotIn(generated_pw, log.old_data or "")
            self.assertNotIn(generated_pw, log.new_data or "")
