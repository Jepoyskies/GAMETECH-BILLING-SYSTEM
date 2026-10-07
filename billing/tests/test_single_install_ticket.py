"""
One install ticket per customer.

THE BUG THIS PINS
-----------------
A concurrent commit (406beb2) added a raw
`JobTicket.objects.create(ticket_type="INSTALLATION", ...)` inside
add_customer, on the theory that the view "created nothing".

It did create something -- dispatch/signals.py ALREADY auto-creates the
INSTALLATION ticket for every new pending customer, and carries a
de-duplication guard that looks for an open INSTALLATION ticket first. The
view's create() bypassed that guard, so every new applicant got TWO install
tickets and dispatchers would handle every job twice.

The existing onboarding test caught it (`2 != 1`), but nothing asserted the
rule directly, so a future "helpful" change could reintroduce it. These tests
state the rule in one place.

WHY ONE TICKET MATTERS
----------------------
Two open INSTALLATION tickets for one customer means:
  * a technician can be dispatched twice for the same address
  * the QA bounce-back counter double-counts
  * "exactly one install ticket" (SPEC) is violated, and the same-person flag
    across stages becomes meaningless
  * marking the customer Installed closes open tickets in bulk
    (customers/actions.py), which then hides the duplicate
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import (
    Barangay, ChecklistConfirmation, Customer, SubscriptionPlan, SystemAdmin,
)
from dispatch.models import JobTicket

User = get_user_model()


class SingleInstallTicketTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="crud_staff",
            password="Compl1ant#Pass!",
            is_staff=True,
            email="crud@gametech.local",
        )
        SystemAdmin.objects.get_or_create(
            username="crud_staff",
            defaults={
                "full_name": "Crud Staff",
                "email": "crud@gametech.local",
                "role": "CSR",
                "status": "Active",
            },
        )
        self.last_response = None
        self.last_detail = ""
        # add_customer is behind @permission_required("billing.add_customer")
        # as well as @role_required, so a role alone is not enough.
        add_perm = Permission.objects.filter(
            content_type__app_label="billing", codename="add_customer",
        ).first()
        self.assertIsNotNone(
            add_perm, "billing.add_customer permission must exist.")
        self.staff.user_permissions.add(add_perm)
        self.staff = User.objects.get(pk=self.staff.pk)

        self.plan = SubscriptionPlan.objects.create(
            name="Plan 1000",
            speed_up="20 Mbps",
            speed_down="20 Mbps",
            price=1000.0,
        )
        self.barangay = Barangay.objects.create(name="Lab")

    def _create_customer_via_view(self, username="dup_guard_sub"):
        """Drive the real add_customer view with a completed checklist."""
        self.client.force_login(self.staff)

        # The checklist guard needs an agreed confirmation keyed on phone.
        ChecklistConfirmation.objects.create(
            applicant_name="Dup Guard",
            applicant_phone="09171230000",
            outcome="agreed",
            method="in_person",
        )

        response = self.client.post(reverse("add_customer"), {
            "full_name": "Dup Guard",
            "phone": "09171230000",
            "address": "1 Test St",
            "email": "dupguard@example.com",
            "pppoe_username": username,
            "pppoe_password": "pw123456",
            "plan": self.plan.id,
            "account_type": 1,
            "barangay": self.barangay.id,
            "latitude": "7.0",
            "longitude": "125.0",
            "installation_status": "pending",
            "status": "pending",
            "created_form_by": "walkin",
            # The checklist confirmation itself
            "checklist_confirmed": "on",
            "item_free_install": "on",
            "item_specific_plan": "on",
            "item_no_lockin": "on",
            "item_staggered_lock": "on",
            "item_same_day_repair": "on",
            "item_rebates_24h": "on",
            "confirm_method": "in_person",
        })
        self.last_response = response
        if response.status_code == 200:
            form_errors = [
                e for e in response.context.get("form", None).errors.as_data().values()
            ] if getattr(response.context.get("form", None), "errors", None) else []
            messages_ = [str(m) for m in response.context["messages"]] \
                if "messages" in response.context else []
            self.last_detail = "{!r} / form errors: {}".format(
                messages_, form_errors)
        return response

    def test_new_customer_gets_exactly_one_install_ticket(self):
        """THE rule. Two would mean dispatchers handle every job twice."""
        self._create_customer_via_view()

        cust = Customer.objects.filter(pppoe_username="dup_guard_sub").first()
        self.assertIsNotNone(
            cust,
            "The customer was not created, so this test proves nothing. "
            "status={} detail={}".format(
                getattr(self.last_response, "status_code", "?"),
                self.last_detail,
            ),
        )

        tickets = JobTicket.objects.filter(
            customer=cust, ticket_type="INSTALLATION",
        )
        self.assertEqual(
            tickets.count(), 1,
            "Expected exactly ONE INSTALLATION ticket, found {}. A duplicate "
            "sends a technician to the same address twice and corrupts the "
            "bounce-back counters.".format(tickets.count()),
        )

    def test_install_ticket_lands_in_the_dispatch_queue(self):
        self._create_customer_via_view()
        cust = Customer.objects.get(pppoe_username="dup_guard_sub")

        ticket = JobTicket.objects.get(
            customer=cust, ticket_type="INSTALLATION",
        )
        self.assertEqual(
            ticket.status, "PENDING",
            "The install ticket must sit in the unassigned queue ready for a "
            "dispatcher.",
        )
        self.assertEqual(ticket.technicians.count(), 0,
                         "A new ticket must not be pre-assigned.")

    def test_no_duplicate_appears_after_a_second_save(self):
        """Re-saving the customer must not spawn another ticket either."""
        self._create_customer_via_view()
        cust = Customer.objects.get(pppoe_username="dup_guard_sub")

        Customer.objects.filter(pk=cust.pk).update(
            address="2 Updated St")

        self.assertEqual(
            JobTicket.objects.filter(
                customer=cust, ticket_type="INSTALLATION",
            ).count(),
            1,
            "Updating a customer spawned a second install ticket.",
        )

    def _last_status(self):
        return "see test output"