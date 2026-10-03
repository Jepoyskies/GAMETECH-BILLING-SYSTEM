"""
Reset command tests.

A reset command is the most dangerous thing in the repo: it deletes real
subscriber data. These tests pin the guarantees that make it safe to run.

THE GUARANTEES
---------------
1. Without --yes it deletes NOTHING.
2. Staff accounts always survive. Losing them loses the logins entirely.
3. The plan catalogue survives. Those 34 plans are the product matrix; the
   legacy importer cannot rebuild the (price, speed) mapping without them.
4. The router fleet survives. 4 devices, each hand-configured with an IP.
5. The routers THEMSELVES are never contacted.
6. Everything else goes: customers, payments, tickets, prospects.
7. It runs in one transaction, so a mid-way failure changes nothing.
"""

from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from billing.models import (
    Barangay, Customer, Payment, Prospect, SubscriptionPlan, SystemAdmin,
    SystemLog,
)
from dispatch.models import JobTicket
from network_manager.models import MikrotikDevice

User = get_user_model()


def make_customer(username="reset_sub"):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name="P1000",
        defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 1000.0},
    )
    barangay, _ = Barangay.objects.get_or_create(name="Lab")
    return Customer.objects.create(
        full_name="Reset Sub",
        pppoe_username=username,
        status="active",
        installation_status="installed",
        plan=plan,
        barangay=barangay,
        expires_at=timezone.now() + timezone.timedelta(days=10),
    )


def seed_activity():
    cust = make_customer()
    Payment.objects.create(
        customer=cust, username=cust.pppoe_username, amount=1000.00,
        payment_method="cash", reference_no="R1",
    )
    JobTicket.objects.create(
        client_name="Reset Sub", ticket_type="INSTALLATION", status="PENDING",
        customer=cust,
    )
    Prospect.objects.create(
        full_name="Walk In Prospect", phone="09170000000",
        status="NEW",
    )
    SystemLog.objects.create(
        table_name="Customer", record_id=str(cust.id), action="ADD",
        changed_by="test", target_name="Reset Sub", old_data="", new_data="x",
    )
    return cust


class ResetSafetyTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="reset_staff", password="Compl1ant#Pass!", is_staff=True)
        User.objects.create_user(
            username="reset_super", password="Compl1ant#Pass!", is_superuser=True)
        self.plan = SubscriptionPlan.objects.create(
            name="KeepMe", speed_up="10 Mbps", speed_down="10 Mbps", price=500.0)
        self.device = MikrotikDevice.objects.create(
            device_name="Keep Router", ip_address="10.0.0.9",
            api_username="admin", api_password="pw", api_port=8728)
        self.barangay = Barangay.objects.create(name="Keep Barangay")
        SystemAdmin.objects.create(
            username="reset_staff", full_name="Reset Staff",
            email="reset@gametech.local", role="Staff", status="Active")

    def _run(self, *args):
        out = StringIO()
        call_command("reset_operational_data", *args, stdout=out)
        return out.getvalue()

    # -- the guard rail ------------------------------------------------
    def test_without_yes_deletes_nothing(self):
        seed_activity()
        before = Customer.objects.count()

        output = self._run()

        self.assertEqual(
            Customer.objects.count(), before,
            "The reset ran without --yes and deleted data. That is the one "
            "failure mode that would destroy a live database.",
        )
        self.assertIn("Nothing was deleted", output)

    def test_yes_prints_the_plan_before_deleting(self):
        seed_activity()
        output = self._run("--yes")
        self.assertIn("RESET PLAN", output)
        self.assertIn("billing.Customer", output)

    # -- what must survive --------------------------------------------
    def test_staff_accounts_always_survive(self):
        seed_activity()
        self._run("--yes")

        for username in ("reset_staff", "reset_super"):
            self.assertTrue(
                User.objects.filter(username=username).exists(),
                "The reset deleted the {} login. Staff accounts ARE the "
                "product.".format(username),
            )

    def test_plan_catalogue_survives(self):
        seed_activity()
        self._run("--yes")
        self.assertTrue(
            SubscriptionPlan.objects.filter(name="KeepMe").exists(),
            "The plan catalogue was deleted. These 34 plans encode the "
            "(price, speed) product matrix and cannot be rebuilt from the "
            "export alone.",
        )

    def test_router_fleet_survives(self):
        seed_activity()
        self._run("--yes")
        self.assertTrue(
            MikrotikDevice.objects.filter(device_name="Keep Router").exists(),
            "A router was deleted from the fleet. Its IP and credentials are "
            "hand-configured.",
        )

    def test_barangays_survive(self):
        seed_activity()
        self._run("--yes")
        self.assertTrue(Barangay.objects.filter(name="Keep Barangay").exists())

    def test_personas_survive(self):
        seed_activity()
        self._run("--yes")
        self.assertTrue(
            SystemAdmin.objects.filter(username="reset_staff").exists(),
            "The staff personas were deleted, so role checks would fail for "
            "everyone.",
        )

    def test_routers_are_never_contacted(self):
        """A database reset must not reach over the network."""
        seed_activity()
        with mock.patch(
            "network_manager.services.MikrotikAPI.__init__"
        ) as api_init:
            self._run("--yes")
        api_init.assert_not_called()

    # -- what must go --------------------------------------------------
    def test_operational_data_is_removed(self):
        seed_activity()
        self._run("--yes")

        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(JobTicket.objects.count(), 0)
        self.assertEqual(Prospect.objects.count(), 0)
        self.assertEqual(SystemLog.objects.count(), 0)

    def test_reset_is_idempotent(self):
        """Running it twice must not error -- resets get re-run."""
        seed_activity()
        self._run("--yes")
        output = self._run("--yes")
        self.assertIn("RESET COMPLETE", output)
        self.assertEqual(Customer.objects.count(), 0)

    def test_reset_works_on_an_already_empty_database(self):
        output = self._run("--yes")
        self.assertIn("RESET COMPLETE", output)

    # -- atomicity -----------------------------------------------------
    def test_failure_rolls_back_everything(self):
        """A mid-way error must leave the database untouched.

        This is the guarantee that makes a reset safe to run on production
        during business hours.
        """
        seed_activity()
        before_customers = Customer.objects.count()
        before_payments = Payment.objects.count()

        real_delete = Customer.objects.all().delete

        def explode(*a, **kw):
            raise RuntimeError("simulated mid-reset failure")

        # Fail on the LAST model so earlier deletes have already run inside
        # the transaction.
        with mock.patch(
            "billing.models.Customer.objects.all",
            side_effect=explode,
        ):
            with self.assertRaises(Exception):
                self._run("--yes")

        self.assertEqual(
            Customer.objects.count(), before_customers,
            "A failed reset still deleted customers. It must roll back.",
        )
        self.assertEqual(
            Payment.objects.count(), before_payments,
            "A failed reset left partial deletions behind.",
        )