from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from django.utils import timezone
from datetime import timedelta

from dispatch.models import (
    JobTicket, JobTicketHistory, Team, Technician, CallAttemptLog, AuditLog
)
from billing.models import Customer, SubscriptionPlan, Barangay, Notification


class DispatchOperationsTestCase(TestCase):
    """
    Automated test suite for Phase 4A Dispatch Operations:
    1. Allowed and forbidden status transitions.
    2. Technicians cannot see or accept unassigned jobs (no self-pick).
    3. Off-duty technicians not offered in assignments; duty toggle endpoint.
    4. Arrived timer with optional GPS and Done timer calculation.
    5. Dispatcher timer correction with mandatory logged reason.
    6. 3-contact attempt rule and return-to-dispatch workflow.
    7. Same-person flag recorded across multi-stage execution.
    8. Role and permission enforcement.
    """

    def setUp(self):
        self.client = Client()
        self.barangay = Barangay.objects.create(name="Bulua Ops Lab")
        self.plan = SubscriptionPlan.objects.create(
            name="Plan 1500",
            speed_up="50 Mbps",
            speed_down="50 Mbps",
            price=1500.00,
        )
        self.customer = Customer.objects.create(
            full_name="Pedro Penduko",
            phone="09181234567",
            address="Zone 3 Bulua",
            barangay=self.barangay,
            plan=self.plan,
            status="active",
            installation_status="installed",
        )

        # Users and Teams
        self.dispatcher_user = User.objects.create_user(
            username="dispatcher_dave",
            password="Compl1ant#Pass!",
            is_staff=True,
        )
        self.tech_user = User.objects.create_user(
            username="tech_tim",
            password="Compl1ant#Pass!",
            is_staff=False,
        )
        self.other_tech_user = User.objects.create_user(
            username="tech_oscar",
            password="Compl1ant#Pass!",
            is_staff=False,
        )

        self.team_alpha = Team.objects.create(name="Team Alpha")
        self.tech_tim = Technician.objects.create(
            name="Tim Rivera",
            contact_number="09170000001",
            team=self.team_alpha,
            is_available=True,
            user=self.tech_user,
        )
        self.tech_oscar = Technician.objects.create(
            name="Oscar Cruz",
            contact_number="09170000002",
            team=self.team_alpha,
            is_available=True,
            user=self.other_tech_user,
        )

    def test_allowed_and_forbidden_transitions(self):
        """Verify lifecycle transition graph: allowed flows vs invalid jumps."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="PENDING",
            client_name="Test Client",
            customer=self.customer,
        )

        # Allowed transitions from PENDING
        self.assertTrue(ticket.can_transition_to("ASSIGNED"))
        self.assertTrue(ticket.can_transition_to("CANCELLED"))

        # Forbidden jumps from PENDING
        self.assertFalse(ticket.can_transition_to("IN_PROGRESS"))
        self.assertFalse(ticket.can_transition_to("COMPLETED"))
        self.assertFalse(ticket.can_transition_to("QA_PASSED"))
        self.assertFalse(ticket.can_transition_to("APPROVED"))

        # Move to ASSIGNED
        ticket.status = "ASSIGNED"
        self.assertTrue(ticket.can_transition_to("IN_PROGRESS"))
        self.assertTrue(ticket.can_transition_to("PENDING"))
        self.assertFalse(ticket.can_transition_to("APPROVED"))

        # Site visit flow: assign -> in_progress -> completed
        site_ticket = JobTicket.objects.create(
            ticket_type="SITE_VISIT",
            status="IN_PROGRESS",
            client_name="Site Client",
        )
        self.assertTrue(site_ticket.can_transition_to("COMPLETED"))

    def test_technicians_cannot_see_or_accept_unassigned_jobs(self):
        """Technicians only see assigned jobs, cannot see unassigned queue, and cannot self-pick."""
        # Create 1 unassigned ticket and 1 assigned ticket
        unassigned_ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="PENDING",
            client_name="Unassigned Applicant",
        )
        assigned_ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="ASSIGNED",
            client_name="Assigned Applicant",
        )
        assigned_ticket.technicians.add(self.tech_tim)

        # Login as technician Tim
        self.client.force_login(self.tech_user)

        response = self.client.get(reverse("technician_mobile_ui"))
        self.assertEqual(response.status_code, 200)

        # Verify only assigned ticket is in technician's view
        tickets_in_view = list(response.context["tickets"])
        self.assertIn(assigned_ticket, tickets_in_view)
        self.assertNotIn(unassigned_ticket, tickets_in_view)

        # Technician attempts to self-pick/assign the unassigned ticket -> 403 Forbidden
        assign_resp = self.client.post(
            reverse("api_dispatch_assign_ticket", args=[unassigned_ticket.id]),
            {"team_id": self.team_alpha.id},
            content_type="application/json",
        )
        self.assertEqual(assign_resp.status_code, 403)
        unassigned_ticket.refresh_from_db()
        self.assertEqual(unassigned_ticket.status, "PENDING")
        self.assertEqual(unassigned_ticket.technicians.count(), 0)

    def test_off_duty_technicians_not_offered(self):
        """Off-duty technicians are excluded from job assignment; duty toggle endpoint works."""
        self.client.force_login(self.dispatcher_user)

        # Toggle Oscar off-duty
        toggle_resp = self.client.post(
            reverse("api_dispatch_toggle_technician_duty", args=[self.tech_oscar.id])
        )
        self.assertEqual(toggle_resp.status_code, 200)
        self.tech_oscar.refresh_from_db()
        self.assertFalse(self.tech_oscar.is_available)

        ticket = JobTicket.objects.create(
            ticket_type="REPAIR",
            status="PENDING",
            client_name="Repair Client",
        )

        # Attempt to assign only the off-duty technician
        assign_resp = self.client.post(
            reverse("api_dispatch_assign_ticket", args=[ticket.id]),
            {"technician_ids": [self.tech_oscar.id]},
            content_type="application/json",
        )
        self.assertEqual(assign_resp.status_code, 400)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "PENDING")

        # Assign active technician Tim -> succeeds
        valid_assign = self.client.post(
            reverse("api_dispatch_assign_ticket", args=[ticket.id]),
            {"technician_ids": [self.tech_tim.id], "scheduled_date": "2026-09-25"},
            content_type="application/json",
        )
        self.assertEqual(valid_assign.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "ASSIGNED")
        self.assertIn(self.tech_tim, ticket.technicians.all())

    def test_timer_and_optional_gps(self):
        """Technician clicking Arrived starts timer with optional GPS; Done stops timer and notifies staff."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="ASSIGNED",
            client_name="Timer Client",
        )
        ticket.technicians.add(self.tech_tim)

        self.client.force_login(self.tech_user)

        # Arrived with optional GPS coords
        arrived_resp = self.client.post(
            reverse("api_dispatch_ticket_arrived", args=[ticket.id]),
            {"latitude": 8.4822, "longitude": 124.6472},
            content_type="application/json",
        )
        self.assertEqual(arrived_resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "IN_PROGRESS")
        self.assertIsNotNone(ticket.arrived_at)
        self.assertIsNotNone(ticket.time_start)
        self.assertAlmostEqual(ticket.arrival_latitude, 8.4822, places=3)
        self.assertAlmostEqual(ticket.arrival_longitude, 124.6472, places=3)

        # Simulate work duration (set start 45 mins ago)
        ticket.time_start = timezone.now() - timedelta(minutes=45)
        ticket.arrived_at = ticket.time_start
        ticket.save()

        # Technician marks Done
        done_resp = self.client.post(
            reverse("api_dispatch_ticket_done", args=[ticket.id]),
            {
                "nap_port": "Port 3",
                "cable_length": "120m",
                "signal_level": "-18.2",
                "technician_report": "Fiber spliced cleanly; ONT provisioned and signal confirmed.",
            },
            content_type="application/json",
        )
        self.assertEqual(done_resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "COMPLETED")
        self.assertIsNotNone(ticket.finished_at)
        self.assertGreaterEqual(ticket.duration, 44)

        # Staff notification was dispatched
        notification = Notification.objects.filter(notification_type="dispatch").first()
        self.assertIsNotNone(notification)
        self.assertIn(ticket.ticket_number, notification.title)

    def test_timer_correction_with_reason(self):
        """Dispatch can adjust a forgotten timer; mandatory reason is required and audited."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="COMPLETED",
            client_name="Correction Client",
            time_start=timezone.now() - timedelta(hours=3),
            time_accomplish=timezone.now() - timedelta(hours=2),
            duration=60,
        )

        self.client.force_login(self.dispatcher_user)

        # Missing reason -> 400 error
        fail_resp = self.client.post(
            reverse("api_dispatch_correct_timer", args=[ticket.id]),
            {"arrived_at": "2026-09-24T14:00:00", "finished_at": "2026-09-24T14:45:00", "reason": ""},
            content_type="application/json",
        )
        self.assertEqual(fail_resp.status_code, 400)

        # Valid correction with mandatory reason
        good_resp = self.client.post(
            reverse("api_dispatch_correct_timer", args=[ticket.id]),
            {
                "arrived_at": "2026-09-24T14:00:00",
                "finished_at": "2026-09-24T14:45:00",
                "reason": "Technician arrived at 2:00 PM; mobile phone battery died on site.",
            },
            content_type="application/json",
        )
        self.assertEqual(good_resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.duration, 45)
        self.assertEqual(ticket.timer_corrected_by, self.dispatcher_user)
        self.assertIn("battery died", ticket.timer_correction_reason)

    def test_3_contact_attempt_rule_and_return_to_dispatch(self):
        """Logging 3 contact attempts unlocks Return to Dispatch; returns notify staff and update customer."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="ASSIGNED",
            client_name="Unreachable Applicant",
            customer=self.customer,
        )
        ticket.technicians.add(self.tech_tim)

        self.client.force_login(self.tech_user)

        # 1st attempt
        r1 = self.client.post(
            reverse("api_dispatch_contact_attempt", args=[ticket.id]),
            {"result": "unanswered", "notes": "No answer after 5 rings."},
            content_type="application/json",
        )
        self.assertEqual(r1.json()["count"], 1)
        self.assertFalse(r1.json()["can_return"])

        # 2nd attempt
        r2 = self.client.post(
            reverse("api_dispatch_contact_attempt", args=[ticket.id]),
            {"result": "busy", "notes": "Line busy."},
            content_type="application/json",
        )
        self.assertEqual(r2.json()["count"], 2)
        self.assertFalse(r2.json()["can_return"])

        # 3rd attempt
        r3 = self.client.post(
            reverse("api_dispatch_contact_attempt", args=[ticket.id]),
            {"result": "unanswered", "notes": "Unattended."},
            content_type="application/json",
        )
        self.assertEqual(r3.json()["count"], 3)
        self.assertTrue(r3.json()["can_return"])

        # Return to Dispatch
        return_resp = self.client.post(
            reverse("api_dispatch_return_to_dispatch", args=[ticket.id]),
            {"reason": "no_contact", "notes": "Customer did not answer after 3 attempts."},
            content_type="application/json",
        )
        self.assertEqual(return_resp.status_code, 200)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "CANCELLED")
        self.assertEqual(ticket.cancellation_reason, "no_contact")

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.installation_status, "closed_not_installed")

    def test_same_person_flag_recorded(self):
        """A user acting on multiple distinct stages automatically sets the same_person_flag."""
        ticket = JobTicket.objects.create(
            ticket_type="INSTALLATION",
            status="PENDING",
            client_name="Audit Flag Client",
        )
        self.assertFalse(ticket.same_person_flag)

        # Stage 1: Assignment by dispatcher_user
        ticket.record_stage_action("ASSIGNMENT", self.dispatcher_user)
        self.assertFalse(ticket.same_person_flag)

        # Stage 2: Same user acts on Field Completion
        ticket.record_stage_action("FIELD_DONE", self.dispatcher_user)
        self.assertTrue(ticket.same_person_flag)
        self.assertEqual(len(ticket.same_person_stages), 2)
