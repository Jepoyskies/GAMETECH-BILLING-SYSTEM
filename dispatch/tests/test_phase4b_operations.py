"""
Test suite for Phase 4B: Dispatch QA, Admin Final Approval, Bounce-Back History,
Admin Summary, 2-Bounce Alerts, Repair Bypass Rule, and Unreachable Close/Reopen Flows.
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from billing.models import Customer, SubscriptionPlan
from dispatch.models import JobTicket, Team, Technician, TicketBounceHistory

User = get_user_model()


class Phase4BOperationsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username="test_admin_phase4b",
            email="admin_4b@gametech.local",
            password="AdminPassword123!",
        )
        self.admin_user.role = "Admin"
        self.admin_user.save()

        # QA Staff user
        self.qa_user = User.objects.create_user(
            username="test_qa_phase4b",
            email="qa_4b@gametech.local",
            password="QaPassword123!",
            is_staff=True,
        )
        self.qa_user.role = "Staff"
        qa_perm = Permission.objects.filter(codename="dispatch_qa").first()
        if qa_perm:
            self.qa_user.user_permissions.add(qa_perm)
        self.qa_user.save()

        # Field Technician User & Profile
        self.tech_user = User.objects.create_user(
            username="test_tech_phase4b",
            email="tech_4b@gametech.local",
            password="TechPassword123!",
        )
        self.tech_user.role = "Technician"
        self.tech_user.save()

        self.team = Team.objects.create(name="Team Alpha 4B", leader="Juan Leader")
        self.technician = Technician.objects.create(
            name="Pedro Field Tech 4B",
            phone="09181112222",
            user=self.tech_user,
            team=self.team,
            is_available=True,
        )

        # Plan & Active Customer Fixture
        self.plan = SubscriptionPlan.objects.create(
            name="Plan 1500 Fast",
            price=1500.00,
            speed="50 Mbps",
        )
        self.customer = Customer.objects.create(
            full_name="Juan Subscriber 4B",
            phone="09170001122",
            address="Poblacion, Cagayan de Oro",
            plan=self.plan,
            status="active",
            installation_status="installed",
            pppoe_username="juan_sub_4b",
        )

    def test_qa_screen_pass_requires_client_called_confirmation(self):
        """Passing QA strictly requires confirming that the client was called."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="COMPLETED",
            client_name="Test Call Client",
            contact_number="09170001122",
            customer=self.customer,
        )
        self.client.force_login(self.qa_user)

        # Fail: client_called missing / False -> HTTP 400
        fail_resp = self.client.post(
            reverse("api_dispatch_qa_review", args=[ticket.id]),
            {"action": "pass", "client_called": False, "qa_notes": "All looks good"},
            content_type="application/json",
        )
        self.assertEqual(fail_resp.status_code, 400)
        self.assertIn("called is required", fail_resp.json().get("error", ""))

        # Pass: client_called True -> HTTP 200, status becomes QA_PASSED
        pass_resp = self.client.post(
            reverse("api_dispatch_qa_review", args=[ticket.id]),
            {"action": "pass", "client_called": True, "qa_notes": "Customer confirmed signal OK"},
            content_type="application/json",
        )
        self.assertEqual(pass_resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "QA_PASSED")
        self.assertTrue(ticket.client_called_by_qa)
        self.assertEqual(ticket.qa_by, self.qa_user)

    def test_qa_bounce_to_technician_requires_reason_and_type(self):
        """Bouncing to technician requires a reason and handles revisit vs correct_report types."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="COMPLETED",
            client_name="Test Bounce Client",
            customer=self.customer,
            time_start=timezone.now() - timedelta(hours=1),
            arrived_at=timezone.now() - timedelta(hours=1),
            time_accomplish=timezone.now(),
            finished_at=timezone.now(),
            duration=60,
        )
        self.client.force_login(self.qa_user)

        # Missing reason -> 400
        fail_resp = self.client.post(
            reverse("api_dispatch_qa_review", args=[ticket.id]),
            {"action": "bounce", "bounce_type": "correct_report", "reason": ""},
            content_type="application/json",
        )
        self.assertEqual(fail_resp.status_code, 400)

        # Bounce type: correct_report -> sets status IN_PROGRESS, preserves timer
        rep_resp = self.client.post(
            reverse("api_dispatch_qa_review", args=[ticket.id]),
            {"action": "bounce", "bounce_type": "correct_report", "reason": "Missing ONT barcode photo"},
            content_type="application/json",
        )
        self.assertEqual(rep_resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "IN_PROGRESS")
        self.assertEqual(ticket.bounce_count, 1)
        self.assertIsNotNone(ticket.arrived_at)

        # Bounce type: revisit -> sets status ASSIGNED, resets timer for new site visit
        ticket.status = "COMPLETED"
        ticket.save()
        rev_resp = self.client.post(
            reverse("api_dispatch_qa_review", args=[ticket.id]),
            {"action": "bounce", "bounce_type": "revisit", "reason": "Customer reported high optical loss. Re-splice required."},
            content_type="application/json",
        )
        self.assertEqual(rev_resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "ASSIGNED")
        self.assertEqual(ticket.bounce_count, 2)
        self.assertIsNone(ticket.arrived_at)
        self.assertIsNone(ticket.time_start)

    def test_alert_after_2_bounces_on_same_job(self):
        """A ticket that bounces 2 or more times triggers repeated_bounce_alert flag."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="COMPLETED",
            client_name="Repeat Bounce Client",
            customer=self.customer,
        )
        self.client.force_login(self.qa_user)

        # First bounce
        self.client.post(
            reverse("api_dispatch_qa_review", args=[ticket.id]),
            {"action": "bounce", "bounce_type": "correct_report", "reason": "First correction"},
            content_type="application/json",
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.bounce_count, 1)
        self.assertFalse(ticket.repeated_bounce_alert)

        # Second bounce
        ticket.status = "COMPLETED"
        ticket.save()
        self.client.post(
            reverse("api_dispatch_qa_review", args=[ticket.id]),
            {"action": "bounce", "bounce_type": "revisit", "reason": "Second correction (splice issue)"},
            content_type="application/json",
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.bounce_count, 2)
        self.assertTrue(ticket.repeated_bounce_alert)

    def test_repairs_skip_admin_approval_unless_bounced_twice_or_flagged(self):
        """Repair tickets skip Admin approval directly to APPROVED unless bounced >=2 times or flagged."""
        self.client.force_login(self.qa_user)

        # 1. Clean repair ticket -> QA pass skips admin approval, goes straight to APPROVED
        clean_repair = JobTicket.objects.create(
            ticket_type="REPAIR",
            status="COMPLETED",
            client_name="Clean Repair Client",
            customer=self.customer,
        )
        clean_resp = self.client.post(
            reverse("api_dispatch_qa_review", args=[clean_repair.id]),
            {"action": "pass", "client_called": True, "qa_notes": "LOS restored OK"},
            content_type="application/json",
        )
        self.assertEqual(clean_resp.status_code, 200)
        clean_repair.refresh_from_db()
        self.assertEqual(clean_repair.status, "APPROVED")

        # 2. Repair ticket bounced twice -> QA pass forwards to QA_PASSED (needs Admin approval)
        bounced_repair = JobTicket.objects.create(
            ticket_type="REPAIR",
            status="COMPLETED",
            client_name="Bounced Repair Client",
            customer=self.customer,
            bounce_count=2,
            repeated_bounce_alert=True,
        )
        bounced_resp = self.client.post(
            reverse("api_dispatch_qa_review", args=[bounced_repair.id]),
            {"action": "pass", "client_called": True, "qa_notes": "Fixed after revisit"},
            content_type="application/json",
        )
        self.assertEqual(bounced_resp.status_code, 200)
        bounced_repair.refresh_from_db()
        self.assertEqual(bounced_repair.status, "QA_PASSED")

        # 3. Repair ticket flagged by QA -> QA pass forwards to QA_PASSED (needs Admin approval)
        flagged_repair = JobTicket.objects.create(
            ticket_type="REPAIR",
            status="COMPLETED",
            client_name="Flagged Repair Client",
            customer=self.customer,
        )
        flagged_resp = self.client.post(
            reverse("api_dispatch_qa_review", args=[flagged_repair.id]),
            {"action": "pass", "client_called": True, "is_flagged": True, "qa_notes": "High fiber cost used"},
            content_type="application/json",
        )
        self.assertEqual(flagged_resp.status_code, 200)
        flagged_repair.refresh_from_db()
        self.assertEqual(flagged_repair.status, "QA_PASSED")
        self.assertTrue(flagged_repair.is_flagged)

    def test_admin_approval_screen_and_bounce_to_dispatch(self):
        """Admin final approval screen allows approve (activates customer) or bounce to dispatch with reason."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="QA_PASSED",
            client_name="Admin Approval Client",
            customer=self.customer,
            client_called_by_qa=True,
        )

        # Non-admin user denied
        self.client.force_login(self.tech_user)
        denied_resp = self.client.post(
            reverse("api_dispatch_admin_approve", args=[ticket.id]),
            {"action": "approve"},
            content_type="application/json",
        )
        self.assertEqual(denied_resp.status_code, 403)

        # Admin user bounces to dispatch without reason -> 400
        self.client.force_login(self.admin_user)
        no_reason_resp = self.client.post(
            reverse("api_dispatch_admin_approve", args=[ticket.id]),
            {"action": "bounce", "reason": ""},
            content_type="application/json",
        )
        self.assertEqual(no_reason_resp.status_code, 400)

        # Admin user bounces to dispatch with reason -> sets ticket status COMPLETED (QA)
        bounce_resp = self.client.post(
            reverse("api_dispatch_admin_approve", args=[ticket.id]),
            {"action": "bounce", "reason": "Signal reading -28 dBm is borderline; request re-check."},
            content_type="application/json",
        )
        self.assertEqual(bounce_resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "COMPLETED")
        self.assertEqual(ticket.bounce_count, 1)

        # Admin user approves -> ticket APPROVED, customer active and installed
        ticket.status = "QA_PASSED"
        ticket.save()
        approve_resp = self.client.post(
            reverse("api_dispatch_admin_approve", args=[ticket.id]),
            {"action": "approve"},
            content_type="application/json",
        )
        self.assertEqual(approve_resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "APPROVED")
        self.assertEqual(ticket.admin_approved_by, self.admin_user)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, "active")
        self.assertEqual(self.customer.installation_status, "installed")

    def test_close_unreachable_flow_and_reopen_onboarding(self):
        """Unreachable close requires client & agent informed; customer becomes Closed - Not Installed; reopen resets."""
        cust = Customer.objects.create(
            full_name="Unreachable Sub 4B",
            phone="09179998877",
            status="active",
            installation_status="installed",
        )
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="IN_PROGRESS",
            client_name="Unreachable Sub 4B",
            customer=cust,
            contact_attempt_count=3,
        )
        self.client.force_login(self.qa_user)

        # Close without client_agent_informed -> 400
        fail_close = self.client.post(
            reverse("api_dispatch_close_unreachable", args=[ticket.id]),
            {"close_reason": "no_contact", "client_agent_informed": False},
            content_type="application/json",
        )
        self.assertEqual(fail_close.status_code, 400)

        # Close with client_agent_informed -> sets CANCELLED, customer closed_not_installed
        ok_close = self.client.post(
            reverse("api_dispatch_close_unreachable", args=[ticket.id]),
            {"close_reason": "no_contact", "client_agent_informed": True, "notes": "Called 3 times, gate locked."},
            content_type="application/json",
        )
        self.assertEqual(ok_close.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "CANCELLED")
        self.assertEqual(ticket.cancellation_reason, "no_contact")
        self.assertTrue(ticket.client_agent_informed)

        cust.refresh_from_db()
        self.assertEqual(cust.installation_status, "closed_not_installed")

        # Reopen customer onboarding
        reopen_resp = self.client.post(
            reverse("api_dispatch_reopen_onboarding", args=[cust.id]),
            content_type="application/json",
        )
        self.assertEqual(reopen_resp.status_code, 200)
        cust.refresh_from_db()
        self.assertEqual(cust.installation_status, "pending_installation")
        self.assertIn("/checklist/", reopen_resp.json().get("redirect_url", ""))

    def test_request_service_modal_site_visit_enters_queue(self):
        """Request service modal creates SITE_VISIT ticket routed to dispatch queue."""
        self.client.force_login(self.qa_user)
        create_resp = self.client.post(
            reverse("api_dispatch_create_ticket"),
            {
                "customer_id": self.customer.id,
                "client_name": self.customer.full_name,
                "ticket_type": "SITE_VISIT",
                "priority": "HIGH",
                "concern": "Ocular survey needed for long drop-wire path.",
            },
            content_type="application/json",
        )
        self.assertEqual(create_resp.status_code, 200)
        data = create_resp.json()
        self.assertTrue(data.get("success"))

        ticket = JobTicket.objects.get(id=data["ticket_id"])
        self.assertEqual(ticket.ticket_type, "SITE_VISIT")
        self.assertEqual(ticket.status, "PENDING")
        self.assertEqual(ticket.source_tab, "CLIENT_CONCERNS")
