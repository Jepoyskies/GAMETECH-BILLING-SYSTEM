"""
Dispatch job-order credit, technician handover, and modem equipment capture.

These cover the three features Sir asked for, and the failure modes that
actually bite in the field: a credit rule that quietly pays an opener who never
finished, a handover that can be recorded with no reason, and a MAC that gets
stored in whatever format the technician typed it in.

No test here touches a MikroTik router. Dispatch is read-only against hardware
by design (AGENTS.md Rule 40).
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone

from billing.models import Customer, CustomerMacHistory, SystemAdmin
from dispatch.models import (
    ConfigOption,
    JobTicket,
    TicketTechnicianAssignment,
    Technician,
)
from dispatch.reports import get_csr_performance_report
from dispatch.utils import normalize_mac, find_mac_conflict


def make_user(username, role="CSR"):
    """Idempotent: several tests legitimately need the same opener twice."""
    existing = User.objects.filter(username=username).first()
    if existing:
        return existing
    user = User.objects.create_user(
        username=username,
        password="Compl1ant#Pass!",
        is_staff=True,
        email=f"{username}@gametech.local",
    )
    SystemAdmin.objects.create(
        username=username,
        full_name=username.title(),
        email=f"{username}@gametech.local",
        role=role,
        status="Active",
    )
    return user


def make_ticket(created_by=None, customer=None, **kwargs):
    return JobTicket.objects.create(
        ticket_type=kwargs.pop("ticket_type", "INSTALLATION"),
        status=kwargs.pop("status", "PENDING"),
        client_name=kwargs.pop("client_name", "Test Client"),
        contact_number="09170000000",
        created_by=created_by,
        customer=customer,
        **kwargs,
    )


class MacNormalizationTests(TestCase):
    """Technicians type MACs every way imaginable. Store one form."""

    def test_accepts_the_three_field_formats(self):
        for raw in ("aa:bb:cc:dd:ee:ff", "AA-BB-CC-DD-EE-FF", "aabbccddeeff",
                    "AA BB CC DD EE FF", "  aAbBcCdDeEfF  "):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_mac(raw), "AA:BB:CC:DD:EE:FF")

    def test_rejects_junk(self):
        for raw in ("", "   ", "not-a-mac", "AA:BB:CC:DD:EE", "AA:BB:CC:DD:EE:FF:00",
                    "ZZ:ZZ:ZZ:ZZ:ZZ:ZZ", None):
            with self.subTest(raw=raw):
                self.assertIsNone(normalize_mac(raw))


class JobOrderCreditTests(TestCase):
    """
    Sir's rule: opener earns 1, closer earns 1, same person earns 2.
    Credit settles ONLY at APPROVED, and both halves settle together.
    """

    def setUp(self):
        self.csr_a = make_user("csr_alpha")
        self.csr_b = make_user("csr_beta")

    def _approve(self, ticket, closer):
        ticket.status = "APPROVED"
        ticket.admin_approved_by = closer
        ticket.admin_approved_at = timezone.now()
        ticket.save()
        return ticket

    def test_same_person_open_and_close_scores_two(self):
        t = self._approve(make_ticket(created_by=self.csr_a), self.csr_a)
        self.assertEqual(t.total_credit, 2)
        self.assertEqual(t.opener_credit, 1)
        self.assertEqual(t.closer_credit, 1)
        self.assertTrue(t.credit_summary["same_person"])

    def test_different_people_score_one_each(self):
        t = self._approve(make_ticket(created_by=self.csr_a), self.csr_b)
        self.assertEqual(t.total_credit, 2)
        self.assertFalse(t.credit_summary["same_person"])

    def test_unapproved_ticket_scores_nobody(self):
        """The anti-farming rule: you cannot bank a point for opening work
        you never intend to finish."""
        for status in ("PENDING", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "QA_PASSED"):
            with self.subTest(status=status):
                t = make_ticket(created_by=self.csr_a, status=status)
                self.assertEqual(t.total_credit, 0)
                self.assertEqual(t.opener_credit, 0)
                self.assertEqual(t.closer_credit, 0)

    def test_cancelled_ticket_scores_nobody(self):
        t = make_ticket(created_by=self.csr_a, status="CANCELLED")
        self.assertEqual(t.total_credit, 0)

    def test_bounced_ticket_scores_nobody(self):
        """A bounce sends status back to COMPLETED, so credit is withdrawn
        from the opener until it is genuinely signed off."""
        t = make_ticket(created_by=self.csr_a, status="COMPLETED")
        t.admin_approved_by = self.csr_b
        t.save()
        self.assertEqual(t.total_credit, 0)

    def test_system_created_ticket_with_no_opener_credits_only_closer(self):
        """Tickets auto-created by the install signal carry created_by=NULL.
        The closer still earned their half."""
        t = self._approve(make_ticket(created_by=None), self.csr_b)
        self.assertEqual(t.total_credit, 1)
        self.assertEqual(t.closer_credit, 1)
        self.assertEqual(t.opener_credit, 0)

    def test_credit_summary_names_both_people(self):
        t = self._approve(make_ticket(created_by=self.csr_a), self.csr_b)
        summary = t.credit_summary
        self.assertEqual(summary["opened_by"], "csr_alpha")
        self.assertEqual(summary["closed_by"], "csr_beta")
        self.assertEqual(summary["points"], 2)


class CsrLeaderboardCreditTests(TestCase):
    """The leaderboard must actually move when a ticket closes."""

    def setUp(self):
        self.csr_a = make_user("leader_a")
        self.csr_b = make_user("leader_b")
        self.csr_c = make_user("leader_c")

    def _close(self, opener, closer):
        t = make_ticket(created_by=opener)
        t.status = "APPROVED"
        t.admin_approved_by = closer
        t.admin_approved_at = timezone.now()
        t.save()

    def _row(self, report, user):
        return next(r for r in report["rows"] if r["user"].id == user.id)

    def test_points_are_split_one_each_for_different_staff(self):
        self._close(self.csr_a, self.csr_b)
        report = get_csr_performance_report()
        a, b = self._row(report, self.csr_a), self._row(report, self.csr_b)
        self.assertEqual(a["points_opened"], 1)
        self.assertEqual(a["points_closed"], 0)
        self.assertEqual(b["points_opened"], 0)
        self.assertEqual(b["points_closed"], 1)
        self.assertEqual(a["points_total"], 1)
        self.assertEqual(b["points_total"], 1)

    def test_same_staff_both_ends_scores_two(self):
        self._close(self.csr_a, self.csr_a)
        report = get_csr_performance_report()
        a = self._row(report, self.csr_a)
        self.assertEqual(a["points_opened"], 1)
        self.assertEqual(a["points_closed"], 1)
        self.assertEqual(a["points_total"], 2)

    def test_ranking_reorders_on_closure(self):
        report = get_csr_performance_report()
        order_before = [r["name"] for r in report["rows"]]
        self.assertIn("leader_a", order_before)
        pos_before = order_before.index("leader_a")

        # leader_c opens AND closes twice: 2 + 2 = 4 points, must overtake.
        self._close(self.csr_c, self.csr_c)
        self._close(self.csr_c, self.csr_c)

        report = get_csr_performance_report()
        order_after = [r["name"] for r in report["rows"]]
        self.assertEqual(order_after[0], "leader_c")
        self.assertLess(order_after.index("leader_c"), pos_before + 1)

    def test_open_tickets_do_not_move_the_leaderboard(self):
        make_ticket(created_by=self.csr_a, status="IN_PROGRESS")
        report = get_csr_performance_report()
        self.assertEqual(self._row(report, self.csr_a)["points_total"], 0)

    def test_closer_who_did_not_open_is_still_listed(self):
        self._close(self.csr_a, self.csr_b)
        report = get_csr_performance_report()
        b = self._row(report, self.csr_b)
        self.assertEqual(b["points_closed"], 1)
        # Closing alone is not "handling" it for throughput purposes.
        self.assertEqual(b["total_handled"], 0)


class TechnicianHandoverTests(TestCase):
    """Ordered handover with a mandatory reason."""

    def setUp(self):
        self.dispatcher = make_user("dispatcher", role="Dispatch")
        self.team_a = Technician.objects.create(name="Tech Alpha")
        self.team_b = Technician.objects.create(name="Tech Beta")
        self.reason = ConfigOption.objects.filter(list_type="REPLACEMENT_REASON").first()
        self.other_reason = ConfigOption.objects.filter(
            list_type="REPLACEMENT_REASON", label__icontains="Other"
        ).first()
        self.client_obj = Client()
        self.client_obj.force_login(self.dispatcher)

    def _assign(self, ticket, tech):
        TicketTechnicianAssignment.objects.create(
            job_ticket=ticket, technician=tech, sequence=1, is_current=True
        )
        ticket.technicians.set([tech.id])
        ticket.save()

    def _replace(self, ticket, outgoing, incoming, reason_id, note=""):
        return self.client_obj.post(
            f"/dispatch/api/tickets/{ticket.id}/replace-technician/",
            data={
                "technician_ids": [str(outgoing.id)],
                "replacement_technician_ids": [str(incoming.id)],
                "replacement_reason_id": str(reason_id or ""),
                "replacement_note": note,
            },
        )

    def test_replacement_requires_a_reason(self):
        t = make_ticket()
        self._assign(t, self.team_a)
        r = self._replace(t, self.team_a, self.team_b, None)
        self.assertEqual(r.status_code, 400)
        self.assertIn("reason", r.json()["error"].lower())

    def test_other_reason_requires_a_note(self):
        t = make_ticket()
        self._assign(t, self.team_a)
        r = self._replace(t, self.team_a, self.team_b, self.other_reason.id, note="")
        self.assertEqual(r.status_code, 400)
        self.assertIn("note", r.json()["error"].lower())

    def test_other_reason_with_note_succeeds(self):
        t = make_ticket()
        self._assign(t, self.team_a)
        r = self._replace(t, self.team_a, self.team_b, self.other_reason.id, note="Customer demanded a specific tech")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["success"], True)

    def test_replacement_records_ordered_history_with_reason(self):
        t = make_ticket()
        self._assign(t, self.team_a)
        self._replace(t, self.team_a, self.team_b, self.reason.id)

        rows = list(t.tech_assignments.select_related("technician", "replacement_reason").order_by("sequence"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].technician.name, "Tech Alpha")
        self.assertEqual(rows[1].technician.name, "Tech Beta")
        self.assertFalse(rows[0].is_current)
        self.assertTrue(rows[1].is_current)
        self.assertEqual(rows[0].replacement_reason, self.reason)
        self.assertEqual(rows[0].replaced_by, self.team_b)
        self.assertEqual(rows[0].stage_label, "replaced")

    def test_technician_cannot_replace_themselves(self):
        t = make_ticket()
        self._assign(t, self.team_a)
        r = self._replace(t, self.team_a, self.team_a, self.reason.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("cannot replace themselves", r.json()["error"])

    def test_replacement_requires_an_incoming_technician(self):
        t = make_ticket()
        self._assign(t, self.team_a)
        r = self.client_obj.post(
            f"/dispatch/api/tickets/{t.id}/replace-technician/",
            data={"technician_ids": [str(self.team_a.id)],
                  "replacement_technician_ids": [],
                  "replacement_reason_id": str(self.reason.id)},
        )
        self.assertEqual(r.status_code, 400)

    def test_m2m_stays_in_sync_with_handover_history(self):
        t = make_ticket()
        self._assign(t, self.team_a)
        self._replace(t, self.team_a, self.team_b, self.reason.id)
        self.assertEqual(list(t.technicians.values_list("id", flat=True)), [self.team_b.id])

    def test_third_technician_continues_the_sequence(self):
        t = make_ticket()
        self._assign(t, self.team_a)
        self._replace(t, self.team_a, self.team_b, self.reason.id)
        team_c = Technician.objects.create(name="Tech Gamma")
        self._replace(t, self.team_b, team_c, self.reason.id)
        seqs = list(t.tech_assignments.order_by("sequence").values_list("sequence", flat=True))
        self.assertEqual(seqs, [1, 2, 3])

    def test_in_progress_ticket_returns_to_assigned_on_replacement(self):
        t = make_ticket(status="IN_PROGRESS")
        self._assign(t, self.team_a)
        self._replace(t, self.team_a, self.team_b, self.reason.id)
        t.refresh_from_db()
        self.assertEqual(t.status, "ASSIGNED")


class ModemEquipmentCaptureTests(TestCase):
    """Feature C: MAC + serial at technician submission, written to the
    customer profile and the equipment history."""

    def setUp(self):
        self.tech_user = make_user("tech_user", role="Dispatch")
        self.tech = Technician.objects.create(name="Field Tech", user=self.tech_user)
        self.customer = Customer.objects.create(
            full_name="Equipment Owner", pppoe_username="equip_owner"
        )
        self.client_obj = Client()
        self.client_obj.force_login(self.tech_user)

    def _submit_done(self, ticket, mac="", sn=""):
        return self.client_obj.post(
            f"/dispatch/api/tickets/{ticket.id}/done/",
            data={
                "ont_modem_mac": mac,
                "ont_modem_sn": sn,
                "technician_report": "Fiber pulled, modem installed and tested.",
            },
            content_type="application/json",
        )

    def _in_progress_ticket(self):
        t = make_ticket(
            created_by=make_user("opener_csx"),
            customer=self.customer,
            status="IN_PROGRESS",
        )
        TicketTechnicianAssignment.objects.create(
            job_ticket=t, technician=self.tech, sequence=1, is_current=True
        )
        t.technicians.set([self.tech.id])
        t.save()
        return t

    def test_submission_writes_mac_to_customer_profile(self):
        t = self._in_progress_ticket()
        self._submit_done(t, mac="aabbccddeeff", sn="ZTEGC1234567")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.mac_address, "AA:BB:CC:DD:EE:FF")

    def test_submission_writes_equipment_history_with_ticket_and_serial(self):
        t = self._in_progress_ticket()
        self._submit_done(t, mac="aa:bb:cc:dd:ee:ff", sn="ZTEGC1234567")
        row = CustomerMacHistory.objects.get(customer=self.customer)
        self.assertEqual(row.mac_address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(row.serial_number, "ZTEGC1234567")
        self.assertEqual(row.source_ticket, t.ticket_number)
        self.assertIn("Initial install", row.replaced_reason)

    def test_invalid_mac_is_rejected_with_a_usable_message(self):
        t = self._in_progress_ticket()
        r = self._submit_done(t, mac="not-a-real-mac", sn="ZTEGC1234567")
        self.assertEqual(r.status_code, 400)
        self.assertIn("not a valid MAC", r.json()["error"])

    def test_replacement_modem_is_traceable_end_to_end(self):
        first = self._in_progress_ticket()
        self._submit_done(first, mac="AA:BB:CC:DD:EE:01", sn="SN-OLD")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.mac_address, "AA:BB:CC:DD:EE:01")

        second = self._in_progress_ticket()
        self._submit_done(second, mac="AA:BB:CC:DD:EE:02", sn="SN-NEW")

        history = list(
            CustomerMacHistory.objects.filter(customer=self.customer)
            .order_by("-detected_at")
        )
        self.assertEqual(len(history), 2)
        newest, oldest = history[0], history[1]
        self.assertEqual(newest.mac_address, "AA:BB:CC:DD:EE:02")
        self.assertEqual(newest.serial_number, "SN-NEW")
        self.assertEqual(newest.source_ticket, second.ticket_number)
        self.assertIn("AA:BB:CC:DD:EE:01", newest.replaced_reason)
        self.assertEqual(oldest.mac_address, "AA:BB:CC:DD:EE:01")
        self.assertEqual(oldest.serial_number, "SN-OLD")

    def test_duplicate_mac_across_customers_is_flagged(self):
        other = Customer.objects.create(full_name="Other Owner", pppoe_username="other_owner")
        other.mac_address = "AA:BB:CC:DD:EE:99"
        other.save()

        t = self._in_progress_ticket()
        r = self._submit_done(t, mac="AA:BB:CC:DD:EE:99", sn="SN-DUP")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.json()["duplicate_mac_warning"])
        self.assertIn("Other Owner", r.json()["duplicate_mac_warning"])

    def test_same_mac_on_same_customer_is_not_a_duplicate(self):
        t = self._in_progress_ticket()
        self._submit_done(t, mac="AA:BB:CC:DD:EE:77", sn="SN-1")
        t2 = self._in_progress_ticket()
        r = self._submit_done(t2, mac="AA:BB:CC:DD:EE:77", sn="SN-1")
        self.assertIsNone(r.json()["duplicate_mac_warning"])

    def test_resubmitting_same_mac_does_not_duplicate_history(self):
        t = self._in_progress_ticket()
        self._submit_done(t, mac="AA:BB:CC:DD:EE:88", sn="SN-A")
        t2 = self._in_progress_ticket()
        self._submit_done(t2, mac="AA:BB:CC:DD:EE:88", sn="SN-A")
        self.assertEqual(
            CustomerMacHistory.objects.filter(customer=self.customer).count(), 1
        )

    def test_ticket_records_normalised_mac(self):
        t = self._in_progress_ticket()
        self._submit_done(t, mac="aabbccddee11", sn="SN-X")
        t.refresh_from_db()
        self.assertEqual(t.ont_modem_mac, "AA:BB:CC:DD:EE:11")

    def test_duplicate_helper_ignores_the_same_customer(self):
        self.customer.mac_address = "AA:BB:CC:DD:EE:55"
        self.customer.save()
        self.assertIsNone(find_mac_conflict("AA:BB:CC:DD:EE:55", self.customer))


class TechnicianSubmissionCreditTests(TestCase):
    """A technician finishing a job must not corrupt the credit ledger."""

    def test_submission_marks_assignment_finished(self):
        tech_user = make_user("tech_finisher", role="Dispatch")
        tech = Technician.objects.create(name="Finisher", user=tech_user)
        t = make_ticket(status="IN_PROGRESS", created_by=make_user("opener_fin"))
        a = TicketTechnicianAssignment.objects.create(
            job_ticket=t, technician=tech, sequence=1, is_current=True
        )
        client_obj = Client()
        client_obj.force_login(tech_user)
        client_obj.post(
            f"/dispatch/api/tickets/{t.id}/done/",
            data={"technician_report": "Done.", "ont_modem_mac": "AA:BB:CC:DD:EE:01"},
            content_type="application/json",
        )
        a.refresh_from_db()
        self.assertIsNotNone(a.finished_at)
        self.assertIsNotNone(a.started_at)