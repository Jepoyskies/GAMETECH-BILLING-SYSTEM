"""
Sync Manager tests -- the bouncer, the comment format, and the write guards.

WHY THIS FILE EXISTS
--------------------
Three defects were found by reading the Sync Manager before going live. Each
one silently damages production data, and none had a test:

1. BULK PUSH WROTE THE WRONG COMMENT. The single-account path built
   "Name | Barangay"; bulk push passed a bare `customer.full_name`. The system
   recognises its own secrets by that separator, so every account touched by
   bulk push became permanently unrecognisable -- which is exactly what the
   "Missing/Invalid Comment" flag was reporting. Not a cosmetic bug.

2. SUCCESSFUL WRITES WERE NOT RECORDED. Neither path set sync_status, so an
   account could be written to the router and still read "Unverified"
   forever, and could never leave the approval queue.

3. AUTO-FIX NEVER ASSIGNED THE ROUTER. An account with a null
   mikrotik_device stayed unlinked after a "successful" fix, so it remained
   invisible on the customers page and reappeared in the queue every time.

Plus a safety gap: bulk delete removed secrets from a live router with no
confirmation and no batch limit.

WHAT IS PINNED
--------------
* One comment format, used by every writer.
* A successful write marks the account Synced AND links the router.
* A refused write is recorded as Blocked -- never silently "successful".
* Unverified / Blocked / unlinked accounts all require human approval.
* Bulk delete refuses real subscribers without explicit confirmation, and
  refuses oversized batches.
* Approving links the router even when the customer had none.

SCOPE: observe-only for the router protocol. No real socket is opened --
ROUTER_MODE=dry_run stubs the MikroTik API in this stack.

RUN
---
    docker compose -p gametech-test -f docker-compose.test.yml \\
        run --rm web python manage.py test network_manager.tests.test_sync_manager
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import (
    Barangay, Customer, SubscriptionPlan, SystemAdmin, SystemLog,
)
from network_manager.models import MikrotikDevice
from network_manager.sync_helpers import (
    account_needs_approval,
    approval_reasons,
    build_router_comment,
    mark_synced,
)

User = get_user_model()


def make_device(name="Test CCR2004 Lab", **over):
    defaults = {
        "device_name": name,
        "ip_address": "10.0.0.1",
        "api_username": "admin",
        "api_password": "pw",
        "api_port": "8728",
    }
    defaults.update(over)
    dev, _ = MikrotikDevice.objects.get_or_create(
        device_name=name,
        defaults={k: v for k, v in defaults.items() if k != "device_name"},
    )
    return dev


def make_operator(username="sync_op", role="Admin"):
    user = User.objects.create_user(
        username=username,
        password="Compl1ant#Pass!",
        is_staff=True,
        email=f"{username}@gametech.local",
    )
    SystemAdmin.objects.get_or_create(
        username=username,
        defaults={
            "full_name": username.title(),
            "email": f"{username}@gametech.local",
            "role": role,
            "status": "Active",
        },
    )
    return user


def make_customer(username="gt_sync01", device=None, **over):
    """Create a customer.

    sync_status is applied with a queryset UPDATE, never through save():
    billing/signals.py stages every Customer save to "Pending" unless the
    caller sets push_to_router, because a save means "something changed, a
    human should push it". Recording an ALREADY-APPROVED account therefore has
    to bypass save() -- which is exactly what mark_synced() does.
    """
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name="GTIPID FIBER 1000",
        defaults={"speed_up": "20 Mbps", "speed_down": "20 Mbps", "price": 1000.0},
    )
    barangay = over.pop("barangay", "__auto__")
    if barangay == "__auto__":
        barangay, _ = Barangay.objects.get_or_create(name="Carmen")

    defaults = {
        "full_name": "Juan Dela Cruz",
        "pppoe_username": username,
        "pppoe_password": "secret123",
        "status": "active",
        "installation_status": "installed",
        "plan": plan,
        "barangay": barangay,
        "address": "12 Mabini St",
        "expires_at": timezone.now() + timezone.timedelta(days=30),
    }
    # Pull the write-bypass fields out of `over` BEFORE it is merged, so they
    # cannot be clobbered by defaults and so they never reach create().
    sync_status = over.pop("sync_status", None)
    force_device = over.pop("mikrotik_device", device)
    force_device_id = over.pop("mikrotik_device_id", None)
    defaults.update(over)

    cust = Customer.objects.create(**defaults)

    updates = {}
    if sync_status:
        updates["sync_status"] = sync_status
        cust.sync_status = sync_status
    if force_device is not None:
        updates["mikrotik_device"] = force_device
        cust.mikrotik_device = force_device
    elif force_device_id is not None:
        updates["mikrotik_device_id"] = force_device_id
        cust.mikrotik_device_id = force_device_id
    if updates:
        Customer.objects.filter(pk=cust.pk).update(**updates)
    return cust


class CommentFormatTests(TestCase):
    """The comment is the receipt that identifies a secret to the system."""

    def test_comment_uses_name_and_barangay(self):
        cust = make_customer()
        self.assertEqual(build_router_comment(cust), "Juan Dela Cruz | Carmen")

    def test_comment_falls_back_to_address_without_barangay(self):
        cust = make_customer(barangay=None, address="88 Colon Ave")
        comment = build_router_comment(cust)
        self.assertIn("Juan Dela Cruz", comment)
        self.assertIn("88 Colon Ave", comment)
        self.assertIn("|", comment)

    def test_comment_always_contains_the_separator(self):
        """A comment with no '|' cannot be parsed back to a customer."""
        cust = make_customer(barangay=None, address="")
        self.assertIn("|", build_router_comment(cust))

    def test_long_address_is_trimmed(self):
        cust = make_customer(barangay=None, address="A" * 200)
        comment = build_router_comment(cust)
        self.assertLessEqual(len(comment), 120)

    def test_comment_is_stripped_of_newlines(self):
        """Mikrotik comments are single-line; a newline would corrupt it."""
        cust = make_customer(full_name="Juan\r\nDela Cruz")
        self.assertNotIn("\n", build_router_comment(cust))
        self.assertNotIn("\r", build_router_comment(cust))


class ApprovalGateTests(TestCase):
    """Existence in both places is not approval."""

    def test_unverified_account_needs_approval(self):
        cust = make_customer(sync_status="Unverified")
        self.assertTrue(
            account_needs_approval(cust),
            "An account never checked against a router must require a human.",
        )

    def test_blocked_account_needs_approval(self):
        cust = make_customer(sync_status="Blocked")
        self.assertTrue(account_needs_approval(cust))

    def test_account_without_router_needs_approval(self):
        cust = make_customer(mikrotik_device=None)
        self.assertTrue(
            account_needs_approval(cust),
            "With no router assigned the account cannot be traced anywhere.",
        )

    def test_synced_and_linked_account_is_approved(self):
        dev = make_device()
        cust = make_customer(mikrotik_device=dev, sync_status="Synced")
        self.assertFalse(account_needs_approval(cust))

    def test_reasons_are_human_readable(self):
        cust = make_customer(mikrotik_device=None, sync_status="Unverified")
        reasons = approval_reasons(cust)
        self.assertTrue(reasons)
        for r in reasons:
            self.assertIsInstance(r, str)
            self.assertTrue(r.strip())

    def test_reasons_mention_blocked_write(self):
        cust = make_customer(mikrotik_device=make_device(),
                             sync_status="Blocked")
        self.assertTrue(
            any("refused" in r for r in approval_reasons(cust)),
            "A Blocked account should say a write was refused.",
        )


class MarkSyncedTests(TestCase):
    """A successful write must be recorded, or the queue never clears."""

    def setUp(self):
        self.device = make_device()
        self.operator = make_operator()

    def test_mark_synced_sets_status_and_links_device(self):
        cust = make_customer(mikrotik_device=None, sync_status="Unverified")
        mark_synced(cust, self.device, self.operator)
        cust.refresh_from_db()

        self.assertEqual(cust.sync_status, "Synced")
        self.assertEqual(
            cust.mikrotik_device_id, self.device.id,
            "Approving must link the account to the router, otherwise it stays "
            "invisible on the customers page forever.",
        )

    def test_mark_synced_writes_an_audit_trail(self):
        cust = make_customer(mikrotik_device=None, sync_status="Unverified")
        mark_synced(cust, self.device, self.operator)

        logs = SystemLog.objects.filter(record_id=str(cust.id),
                                        action="ROUTER_SYNC")
        self.assertEqual(
            logs.count(), 1,
            "Every router approval must be attributable to a person.",
        )
        self.assertEqual(logs.first().changed_by, self.operator.username)
        self.assertIn(self.device.device_name, logs.first().new_data)

    def test_mark_synced_records_the_transition(self):
        cust = make_customer(mikrotik_device=None, sync_status="Blocked")
        mark_synced(cust, self.device, self.operator)
        log = SystemLog.objects.filter(action="ROUTER_SYNC").first()
        # The audit line must show where the account came FROM, otherwise a
        # reviewer cannot tell whether the router write actually fixed anything.
        self.assertIn("Blocked", log.new_data)
        self.assertIn("Synced", log.new_data)

    def test_mark_synced_is_idempotent_on_status(self):
        cust = make_customer(mikrotik_device=self.device, sync_status="Synced")
        mark_synced(cust, self.device, self.operator)
        cust.refresh_from_db()
        self.assertEqual(cust.sync_status, "Synced")


class SyncWriteActionTests(TestCase):
    """The POST handlers, with the MikroTik API stubbed."""

    def setUp(self):
        self.device = make_device()
        self.operator = make_operator()
        self.client.force_login(self.operator)

    def _api_ok(self):
        # `return` is a reserved word, so the mock's return_value has to be set
        # after construction rather than as a keyword argument.
        add = mock.MagicMock()
        add.return_value = {"success": True, "message": "ok"}
        delete = mock.MagicMock()
        delete.return_value = {"success": True, "message": "deleted"}
        return mock.MagicMock(
            add_pppoe_user=add,
            delete_pppoe_user=delete,
        )

    def _api_read_only(self):
        add = mock.MagicMock()
        add.return_value = {"success": False, "error": "Blocked by read_only mode"}
        delete = mock.MagicMock()
        delete.return_value = {"success": False, "error": "Blocked by read_only mode"}
        return mock.MagicMock(
            add_pppoe_user=add,
            delete_pppoe_user=delete,
        )

    def _patch_api(self, api):
        """Patch the API class the view imports INSIDE each handler.

        The handlers do a function-local `from network_manager.sync_services
        import MikrotikAPI as MikrotikSyncAPI`, so the module attribute does
        not exist until the handler runs. Patching the source module is the
        reliable target.
        """
        return mock.patch(
            "network_manager.sync_services.MikrotikAPI", return_value=api
        )

    # -- autofix ------------------------------------------------------
    def test_autofix_links_a_customer_that_had_no_router(self):
        """DEFECT 3: Auto-Fix used to succeed but leave the account unlinked."""
        cust = make_customer("gt_unlinked", mikrotik_device=None,
                             sync_status="Unverified")
        self.assertIsNone(cust.mikrotik_device_id)

        with self._patch_api(self._api_ok()):
            self.client.post(
                reverse("sync_autofix_user", args=[self.device.id]),
                {"pppoe_username": "gt_unlinked"},
            )

        cust.refresh_from_db()
        self.assertEqual(
            cust.mikrotik_device_id, self.device.id,
            "Auto-Fix reported success but never assigned the router, so the "
            "account stayed invisible and re-queued forever.",
        )
        self.assertEqual(cust.sync_status, "Synced")

    def test_autofix_writes_the_canonical_comment(self):
        """DEFECT 1: bulk push wrote a bare name instead of 'Name | Barangay'."""
        cust = make_customer("gt_comment", mikrotik_device=self.device)
        api = self._api_ok()

        with self._patch_api(api):
            self.client.post(
                reverse("sync_autofix_user", args=[self.device.id]),
                {"pppoe_username": "gt_comment"},
            )

        comment = api.add_pppoe_user.call_args.kwargs["comment"]
        self.assertEqual(
            comment, "Juan Dela Cruz | Carmen",
            "The router comment must identify the customer with the separator "
            "the system parses.",
        )
        self.assertIn("|", comment)

    def test_autofix_blocked_by_read_only_marks_blocked(self):
        cust = make_customer("gt_ro", mikrotik_device=self.device,
                             sync_status="Unverified")

        with self._patch_api(self._api_read_only()):
            self.client.post(
                reverse("sync_autofix_user", args=[self.device.id]),
                {"pppoe_username": "gt_ro"},
            )

        cust.refresh_from_db()
        self.assertEqual(
            cust.sync_status, "Blocked",
            "A refused write must be recorded, not left looking successful.",
        )
        self.assertNotEqual(
            cust.sync_status, "Synced",
            "read_only must never produce a Synced record.",
        )

    def test_autofix_failure_marks_failed(self):
        cust = make_customer("gt_fail", mikrotik_device=self.device)
        add = mock.MagicMock()
        add.return_value = {"success": False, "error": "no such resource"}
        api = mock.MagicMock(add_pppoe_user=add)
        with self._patch_api(api):
            self.client.post(
                reverse("sync_autofix_user", args=[self.device.id]),
                {"pppoe_username": "gt_fail"},
            )
        cust.refresh_from_db()
        self.assertEqual(cust.sync_status, "Failed")

    # -- bulk push ----------------------------------------------------
    def test_bulk_push_uses_the_same_comment_as_single_push(self):
        """DEFECT 1, the bulk half: this was the source of the bad comments."""
        make_customer("gt_bulk1", mikrotik_device=self.device)
        make_customer("gt_bulk2", mikrotik_device=self.device,
                      full_name="Maria Reyes")
        api = self._api_ok()

        with self._patch_api(api):
            self.client.post(
                reverse("sync_bulk_action", args=[self.device.id]),
                {"bulk_action": "bulk_push",
                 "selected_users": ["gt_bulk1", "gt_bulk2"]},
            )

        comments = [c.kwargs["comment"]
                    for c in api.add_pppoe_user.call_args_list]
        self.assertEqual(len(comments), 2)
        for c in comments:
            self.assertIn("|", c)
        self.assertIn("Juan Dela Cruz | Carmen", comments)

    def test_bulk_push_marks_each_account_synced(self):
        """DEFECT 2: writes succeeded but the DB kept saying Unverified."""
        make_customer("gt_b1", mikrotik_device=self.device,
                      sync_status="Unverified")
        with self._patch_api(self._api_ok()):
            self.client.post(
                reverse("sync_bulk_action", args=[self.device.id]),
                {"bulk_action": "bulk_push", "selected_users": ["gt_b1"]},
            )

        cust = Customer.objects.get(pppoe_username="gt_b1")
        self.assertEqual(
            cust.sync_status, "Synced",
            "A successful bulk push must clear the account from the queue.",
        )

    def test_bulk_push_under_read_only_marks_blocked_not_synced(self):
        make_customer("gt_b2", mikrotik_device=self.device,
                      sync_status="Unverified")
        with self._patch_api(self._api_read_only()):
            self.client.post(
                reverse("sync_bulk_action", args=[self.device.id]),
                {"bulk_action": "bulk_push", "selected_users": ["gt_b2"]},
            )

        cust = Customer.objects.get(pppoe_username="gt_b2")
        self.assertEqual(cust.sync_status, "Blocked")
        self.assertNotEqual(cust.sync_status, "Synced")

    def test_bulk_push_counts_failures_rather_than_claiming_success(self):
        add = mock.MagicMock()
        add.return_value = {"success": False, "error": "Blocked by read_only mode"}
        api = mock.MagicMock(add_pppoe_user=add)
        make_customer("gt_b3", mikrotik_device=self.device)
        with self._patch_api(api):
            self.client.post(
                reverse("sync_bulk_action", args=[self.device.id]),
                {"bulk_action": "bulk_push", "selected_users": ["gt_b3"]},
            )
        self.assertEqual(
            Customer.objects.get(pppoe_username="gt_b3").sync_status, "Blocked"
        )

    def test_bulk_push_skips_unknown_username(self):
        make_customer("gt_b4", mikrotik_device=self.device)
        with self._patch_api(self._api_ok()):
            self.client.post(
                reverse("sync_bulk_action", args=[self.device.id]),
                {
                    "bulk_action": "bulk_push",
                    "selected_users": ["gt_b4", "ghost_not_in_system"],
                },
            )
        # Must not raise, and must not invent a customer.
        self.assertFalse(
            Customer.objects.filter(pppoe_username="ghost_not_in_system").exists()
        )

    # -- bulk delete safety -------------------------------------------
    def test_bulk_delete_refuses_real_subscribers_without_confirmation(self):
        cust = make_customer("gt_del", mikrotik_device=self.device)
        api = self._api_ok()

        with self._patch_api(api):
            self.client.post(
                reverse("sync_bulk_action", args=[self.device.id]),
                {"bulk_action": "bulk_delete", "selected_users": ["gt_del"]},
            )

        api.delete_pppoe_user.assert_not_called()
        self.assertTrue(
            Customer.objects.filter(pppoe_username="gt_del").exists(),
            "Deleting a real subscriber's secret cuts their internet; it must "
            "require explicit confirmation.",
        )

    def test_bulk_delete_proceeds_with_explicit_confirmation(self):
        cust = make_customer("gt_del2", mikrotik_device=self.device)
        api = self._api_ok()

        with self._patch_api(api):
            self.client.post(
                reverse("sync_bulk_action", args=[self.device.id]),
                {
                    "bulk_action": "bulk_delete",
                    "selected_users": ["gt_del2"],
                    "confirm_delete_subscribers": "yes",
                },
            )

        api.delete_pppoe_user.assert_called_once_with(name="gt_del2")
        # The SYSTEM row survives; only the router secret was removed.
        self.assertTrue(Customer.objects.filter(pppoe_username="gt_del2").exists())

    def test_bulk_delete_refuses_an_oversized_batch(self):
        api = self._api_ok()
        many = [f"gt_bulkdel{i}" for i in range(40)]
        with self._patch_api(api):
            self.client.post(
                reverse("sync_bulk_action", args=[self.device.id]),
                {"bulk_action": "bulk_delete", "selected_users": many},
            )
        api.delete_pppoe_user.assert_not_called()

    def test_bulk_delete_allows_unknown_orphans_without_confirmation(self):
        """An orphan secret nobody claims can be cleared freely."""
        api = self._api_ok()
        with self._patch_api(api):
            self.client.post(
                reverse("sync_bulk_action", args=[self.device.id]),
                {"bulk_action": "bulk_delete", "selected_users": ["orphan_secret"]},
            )
        api.delete_pppoe_user.assert_called_once_with(name="orphan_secret")


class SyncManagerPageTests(TestCase):
    """The queue itself must show unapproved accounts."""

    def setUp(self):
        self.device = make_device()
        self.operator = make_operator()
        self.client.force_login(self.operator)

    def _router_payload(self, users):
        fetch = mock.MagicMock()
        fetch.return_value = {"success": True, "data": users}
        return mock.MagicMock(get_all_pppoe_users=fetch)

    def test_unverified_account_is_queued_not_shown_as_active(self):
        """The bouncer: present in both must still await a human."""
        make_customer("gt_queue", mikrotik_device=self.device,
                      sync_status="Unverified")
        api = self._router_payload([{
            "name": "gt_queue", "profile": "GTIPID FIBER 1000",
            "password": "secret123", "comment": "Juan Dela Cruz | Carmen",
            "disabled": "false", "is_active": True, "is_suspicious": False,
        }])

        with mock.patch("network_manager.sync_services.MikrotikAPI",
                        return_value=api):
            response = self.client.get(
                reverse("sync_manager", args=[self.device.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("gt_queue", [u["name"] for u in response.context["needs_review"]])
        self.assertNotIn("gt_queue", [u["name"] for u in response.context["synced"]])

    def test_synced_account_leaves_the_queue(self):
        make_customer("gt_ok", mikrotik_device=self.device, sync_status="Synced")
        api = self._router_payload([{
            "name": "gt_ok", "profile": "GTIPID FIBER 1000",
            "password": "secret123", "comment": "Juan Dela Cruz | Carmen",
            "disabled": "false", "is_active": True, "is_suspicious": False,
        }])

        with mock.patch("network_manager.sync_services.MikrotikAPI",
                        return_value=api):
            response = self.client.get(
                reverse("sync_manager", args=[self.device.id]))

        self.assertIn("gt_ok", [u["name"] for u in response.context["synced"]])

    def test_enabled_secret_is_not_reported_as_cut_off(self):
        """Mikrotik returns disabled as the STRING 'false'.

        bool("false") is True, so before this fix every single secret was
        treated as disabled and every paying customer was queued as
        "Paid, Cut Off". An approved, enabled, in-sync account must sit in
        Synced, not in the review queue.
        """
        make_customer("gt_enabled", mikrotik_device=self.device,
                      sync_status="Synced")
        api = self._router_payload([{
            "name": "gt_enabled", "profile": "GTIPID FIBER 1000",
            "password": "secret123", "comment": "Juan Dela Cruz | Carmen",
            "disabled": "false", "is_active": True, "is_suspicious": False,
        }])

        with mock.patch("network_manager.sync_services.MikrotikAPI",
                        return_value=api):
            response = self.client.get(
                reverse("sync_manager", args=[self.device.id]))

        queued = {u["name"]: u for u in response.context["needs_review"]}
        if "gt_enabled" in queued:
            self.assertFalse(
                queued["gt_enabled"]["router_disabled"],
                "A secret whose MikroTik disabled flag is the string 'false' "
                "must NOT be reported as cut off.",
            )

    def test_disabled_secret_is_still_detected(self):
        """The other direction: a genuinely cut-off paying customer."""
        make_customer("gt_cut", mikrotik_device=self.device,
                      sync_status="Synced")
        api = self._router_payload([{
            "name": "gt_cut", "profile": "GTIPID FIBER 1000",
            "password": "secret123", "comment": "Juan Dela Cruz | Carmen",
            "disabled": "true", "is_active": False, "is_suspicious": False,
        }])

        with mock.patch("network_manager.sync_services.MikrotikAPI",
                        return_value=api):
            response = self.client.get(
                reverse("sync_manager", args=[self.device.id]))

        queued = {u["name"]: u for u in response.context["needs_review"]}
        self.assertIn("gt_cut", queued)
        self.assertTrue(queued["gt_cut"]["router_disabled"])
        self.assertTrue(
            queued["gt_cut"]["state_mismatch"],
            "A paid customer whose secret is disabled is an outage and must "
            "be visible as one.",
        )

    def test_connected_but_unpaid_is_detected(self):
        """Lapsed in the system, still enabled on the router -> collect."""
        make_customer("gt_unpaid", mikrotik_device=self.device,
                      sync_status="Synced",
                      expires_at=timezone.now() - timezone.timedelta(days=10))
        api = self._router_payload([{
            "name": "gt_unpaid", "profile": "GTIPID FIBER 1000",
            "password": "secret123", "comment": "Juan Dela Cruz | Carmen",
            "disabled": "false", "is_active": True, "is_suspicious": False,
        }])

        with mock.patch("network_manager.sync_services.MikrotikAPI",
                        return_value=api):
            response = self.client.get(
                reverse("sync_manager", args=[self.device.id]))

        queued = {u["name"]: u for u in response.context["needs_review"]}
        self.assertIn("gt_unpaid", queued)
        self.assertTrue(
            queued["gt_unpaid"]["connected_but_unpaid"],
            "An unpaid but still-connected subscriber must be flagged for "
            "collection, not suspension.",
        )

    def test_account_with_no_router_is_still_listed(self):
        make_customer("gt_nolink", mikrotik_device=None, sync_status="Unverified")
        api = self._router_payload([{
            "name": "gt_nolink", "profile": "GTIPID FIBER 1000",
            "password": "secret123", "comment": "Juan Dela Cruz | Carmen",
            "disabled": "false", "is_active": True, "is_suspicious": False,
        }])

        with mock.patch("network_manager.sync_services.MikrotikAPI",
                        return_value=api):
            response = self.client.get(
                reverse("sync_manager", args=[self.device.id]))

        queued = {u["name"]: u for u in response.context["needs_review"]}
        self.assertIn("gt_nolink", queued)
        self.assertTrue(
            queued["gt_nolink"]["unlinked"],
            "An account with no router must be flagged as unlinked so staff "
            "know approving will assign one.",
        )

    def test_router_outage_does_not_empty_the_queue(self):
        """A dead router must not read as 'everything is approved'."""
        make_customer("gt_down", mikrotik_device=self.device,
                      sync_status="Unverified")
        fetch = mock.MagicMock()
        fetch.return_value = {"success": False, "error": "timed out"}
        api = mock.MagicMock(get_all_pppoe_users=fetch)
        with mock.patch("network_manager.sync_services.MikrotikAPI",
                        return_value=api):
            response = self.client.get(
                reverse("sync_manager", args=[self.device.id]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            response.context["api_success"],
            "A router timeout must be reported, never treated as agreement.",
        )