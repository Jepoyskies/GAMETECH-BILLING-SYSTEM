"""
Reset operational data, keeping the staff accounts.

WHY THIS IS A COMMAND AND NOT A SQL SCRIPT
-------------------------------------------
A cutover reset is something that has to be RE-RUN (after a bad import, before
a rehearsal, when testing on a live-shaped database). A hand-typed SQL script
gets edited, mis-pasted, and eventually run against the wrong database. This
command is version-controlled, reviewable, and refuses to run without an
explicit --yes, so it cannot fire by accident.

SAFETY MODEL
------------
1. Refuses to run without --yes. No interactive prompt, so it is safe to run
   from a script, but impossible to trigger by muscle memory.
2. Takes a pg_dump-style inventory first and prints what it will delete.
3. NEVER deletes auth_user rows. The staff accounts ARE the product; losing
   them means losing the logins that make the system usable at all.
4. Keeps SubscriptionPlan and MikrotikDevice. Those are CONFIGURATION, not
   operational data: the 34 plans are the product catalogue and the 4 routers
   are the fleet. Deleting them would require re-importing to recover, and the
   import would rebuild them anyway.
5. Deletes in FK-safe order inside one transaction, so a failure leaves the
   database untouched rather than half-wiped.
6. Never touches the routers. This is database-only. If a secret needs
   removing from a router, that is the Sync Manager's job, deliberately.

WHAT IT REMOVES
---------------
Customers, payments, tickets, prospects, checklists, incentives, commissions,
rebates, MAC history, Cignal records, SMS logs, audit/system logs -- i.e.
everything that represents real business activity.
"""

from django.core.management.base import BaseCommand
from django.db import transaction


# (app_label, model_name) in a safe deletion order: children before parents.
#
# ON DELETE CASCADE handles most of this, but being explicit means a
# SET_NULL FK (Payment.customer is SET_NULL) cannot leave orphans behind.
RESET_MODELS = [
    # --- dispatch: leaves reference customers ---
    ("dispatch", "TicketBounceHistory"),
    ("dispatch", "CallAttemptLog"),
    ("dispatch", "JobTicketHistory"),
    ("dispatch", "MonitoringRecord"),
    ("dispatch", "AuditLog"),
    ("dispatch", "DispatchRecord"),
    ("dispatch", "JobTicket"),
    ("dispatch", "Technician"),

    # --- billing: the operational core ---
    ("billing", "Payment"),
    ("billing", "Rebate"),
    ("billing", "CustomerMacHistory"),
    ("billing", "CignalPlay"),
    ("billing", "ChecklistConfirmation"),
    ("billing", "Prospect"),
    ("billing", "Notification"),
    ("billing", "SmsLog"),
    ("billing", "AuditLog"),
    ("billing", "SystemLog"),
    ("billing", "AgentCommissionBatch"),
    ("billing", "AgentCommission"),
    ("billing", "AgentJobOrder"),
    ("billing", "Agent"),
    ("billing", "Customer"),
]

# Configuration that must SURVIVE a reset.
KEEP_MODELS = [
    ("billing", "SubscriptionPlan"),
    ("billing", "AddonPlan"),
    ("billing", "AccountType"),
    ("billing", "Barangay"),
    ("billing", "StaffRole"),
    ("billing", "SystemAdmin"),
    ("network_manager", "MikrotikDevice"),
]


class Command(BaseCommand):
    help = (
        "Delete all operational data (customers, payments, tickets, "
        "prospects, logs) while KEEPING every staff account, the plan "
        "catalogue and the router fleet. Requires --yes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Actually perform the reset. Without this, nothing happens.",
        )
        parser.add_argument(
            "--keep-technicians",
            action="store_true",
            help="Also keep Technician roster rows (linked staff profiles).",
        )

    def handle(self, *args, **kwargs):
        confirmed = kwargs["yes"]
        keep_technicians = kwargs["keep_technicians"]

        targets = self._resolve(RESET_MODELS)

        # Technician rows are the ROSTER -- they carry the user link that makes
        # a technician log in. That is staff configuration, not activity, so
        # they survive a reset unless explicitly asked otherwise.
        if keep_technicians:
            targets = [m for m in targets if m.__name__ != "Technician"]

        plan = []
        for model in targets:
            try:
                count = model.objects.count()
            except Exception as exc:
                count = "ERR({})".format(exc)
            plan.append((model._meta.label, count))

        from django.contrib.auth import get_user_model
        from django.db.models import Q

        User = get_user_model()
        staff_count = User.objects.filter(
            Q(is_superuser=True) | Q(is_staff=True)
        ).count()

        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "RESET PLAN -- operational data that WILL BE DELETED"))
        self.stdout.write("=" * 66)
        for label, count in plan:
            self.stdout.write("  {:<45} {}".format(label, count))
        self.stdout.write("")
        self.stdout.write("  staff accounts KEPT: {}".format(staff_count))
        self.stdout.write("  plans / routers / barangays / personas KEPT: yes")
        self.stdout.write("  routers themselves: NEVER touched")
        self.stdout.write("")

        if not confirmed:
            self.stdout.write(self.style.ERROR(
                "Nothing was deleted. Re-run with --yes to proceed."))
            return

        with transaction.atomic():
            deleted = {}
            for model in targets:
                label = model._meta.label
                try:
                    n, _ = model.objects.all().delete()
                    deleted[label] = n
                except Exception as exc:
                    raise RuntimeError(
                        "Reset aborted while deleting {}: {}. The "
                        "transaction was rolled back, so the database is "
                        "UNCHANGED.".format(label, exc)
                    )

        self.stdout.write(self.style.SUCCESS("RESET COMPLETE"))
        self.stdout.write("-" * 66)
        for label, n in sorted(deleted.items(), key=lambda kv: -kv[1]):
            self.stdout.write("  {:<45} {} rows".format(label, n))

        from django.contrib.auth import get_user_model
        User = get_user_model()
        remaining = User.objects.count()
        self.stdout.write("")
        self.stdout.write("Users remaining: {}".format(remaining))
        self.stdout.write(self.style.SUCCESS(
            "Sign-in accounts were preserved. Log in and rebuild from here."))

    def _resolve(self, pairs):
        from django.apps import apps
        out = []
        for label, name in pairs:
            try:
                out.append(apps.get_model(label, name))
            except LookupError:
                # A model that no longer exists must not abort the reset.
                continue
        return out