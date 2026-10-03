from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from billing.models import Prospect, Customer, SystemAdmin, Payment, Rebate
from dispatch.models import JobTicket


# Django's AUTO-generated model permissions ("add_payment", "change_customer",
# "delete_customer", ...) already exist in auth_permission but were never in
# DISPATCH_PERMISSIONS, so ROLE_PERMISSION_MATRIX could not grant them. Several
# views are gated by `@permission_required("billing.add_payment")` etc., which
# meant every non-superuser got a hard 403 on taking a payment, suspending a
# customer, recording a rebate or deleting a customer -- while the Role Editor
# showed those roles as fully permitted.
#
# These are listed so the matrix stays the single source of truth and the
# command can resolve them. They are looked up from auth_permission, NOT
# created.
AUTO_PERMISSION_CODENAMES = {
    "billing.add_payment",
    "billing.change_customer",
    "billing.delete_customer",
    "billing.add_rebate",
    "billing.add_rollback",
}

# Counter operations every Staff/CSR must be able to perform.
COUNTER_PERMISSIONS = [
    "billing.add_payment",
    "billing.change_customer",
    "billing.add_rebate",
    "billing.add_rollback",
]

# Destructive: office/admin only, never the counter staff.
ADMIN_ONLY_PERMISSIONS = [
    "billing.delete_customer",
]


DISPATCH_PERMISSIONS = {
    # billing / prospect permissions
    "submit_prospect": ("Can submit prospect referrals", Prospect),
    "view_own_referrals": ("Can view own referral leads and progress", Prospect),
    "manage_prospects": ("Can view and manage prospect inbox", Prospect),
    "run_checklist": ("Can execute onboarding policy checklist", Prospect),
    "create_customer": ("Can convert prospect and create customer", Prospect),
    "change_agent": ("Can change customer assigned sales agent", Customer),
    "change_customer_agent": ("Can change customer assigned sales agent", Customer),
    "mark_payout_paid": ("Can approve and mark agent payout batches as paid", Customer),
    "manage_message_templates": ("Can configure SMS and notification templates", Customer),
    "add_existing_subscriber": ("Can add installed/existing subscriber with manual override", Customer),
    # dispatch / job ticket permissions
    "assign_technicians": ("Can assign technicians to job tickets", JobTicket),
    "technician_job_actions": ("Can execute field technician mobile job actions", JobTicket),
    "correct_timers": ("Can adjust technician arrived/done timers", JobTicket),
    "dispatch_qa": ("Can review field reports and QA job tickets", JobTicket),
    "admin_approve": ("Can grant final admin sign-off on jobs", JobTicket),
    "view_bounce_summary": ("Can view bounce-back summary and pattern metrics", JobTicket),
}

ROLE_PERMISSION_MATRIX = {
    "Agent": [
        "submit_prospect",
        "view_own_referrals",
    ],
    "Technician": [
        "technician_job_actions",
    ],
    "Dispatch": [
        "manage_prospects",
        "run_checklist",
        "assign_technicians",
        "correct_timers",
        "dispatch_qa",
    ],
    "Staff": [
        "manage_prospects",
        "run_checklist",
        "create_customer",
        "change_agent",
        "change_customer_agent",
        "manage_message_templates",
    ] + COUNTER_PERMISSIONS + ADMIN_ONLY_PERMISSIONS,
    "CSR": [
        "manage_prospects",
        "run_checklist",
        "create_customer",
        "change_agent",
        "change_customer_agent",
        "manage_message_templates",
    ] + COUNTER_PERMISSIONS,
    "Admin": list(DISPATCH_PERMISSIONS.keys()) + COUNTER_PERMISSIONS + ADMIN_ONLY_PERMISSIONS,
}


class Command(BaseCommand):
    help = "Seeds the 14 named permissions and role matrix for the 5 Dispatch Operation personas"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Setting up Dispatch Operation permissions & role groups..."))

        # 1. Create or retrieve Permissions
        perm_objs = {}
        for codename, (name, model_class) in DISPATCH_PERMISSIONS.items():
            ct = ContentType.objects.get_for_model(model_class)
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=ct,
                defaults={"name": name},
            )
            if not created and perm.name != name:
                perm.name = name
                perm.save()
            perm_objs[codename] = perm

        self.stdout.write(self.style.SUCCESS(f"Verified {len(perm_objs)} named permissions."))

        # 1b. Resolve Django's auto model permissions named in the matrix
        #     ("billing.add_payment" etc). These already exist; we only look
        #     them up. Without this the matrix silently drops them.
        missing_auto = []
        for label in sorted(AUTO_PERMISSION_CODENAMES):
            app_label, codename = label.split(".", 1)
            perm = Permission.objects.filter(
                codename=codename,
                content_type__app_label=app_label,
            ).first()
            if perm:
                perm_objs[label] = perm
            else:
                missing_auto.append(label)
        if missing_auto:
            raise SystemExit(
                "ABORT: these permissions do not exist in auth_permission, so the "
                f"role matrix would silently drop them: {missing_auto}. Run "
                "`manage.py migrate` first so Django creates the model permissions."
            )
        self.stdout.write(
            self.style.SUCCESS(f"Resolved {len(AUTO_PERMISSION_CODENAMES)} auto model permissions.")
        )

        # 2. Create Groups and assign permissions
        for role_name, perms in ROLE_PERMISSION_MATRIX.items():
            group, created = Group.objects.get_or_create(name=role_name)
            unresolved = [p for p in perms if p not in perm_objs]
            if unresolved:
                raise SystemExit(
                    f"ABORT: role '{role_name}' references permissions that do not "
                    f"resolve: {unresolved}. Refusing to write a partial group."
                )
            group_perms = [perm_objs[p] for p in perms]
            group.permissions.set(group_perms)
            group.save()
            status_str = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"[{status_str}] Group '{role_name}' with {len(group_perms)} permissions."))

        # 3. Synchronize existing Users to Groups based on role attribute or SystemAdmin
        synced_count = 0
        for user in User.objects.all():
            role = getattr(user, "role", None)
            if not role:
                admin = SystemAdmin.objects.filter(username__iexact=user.username).first()
                if admin:
                    role = admin.role

            if user.is_superuser:
                admin_group = Group.objects.filter(name="Admin").first()
                if admin_group:
                    user.groups.add(admin_group)
                    synced_count += 1
            elif role and role in ROLE_PERMISSION_MATRIX:
                group = Group.objects.filter(name=role).first()
                if group:
                    user.groups.add(group)
                    synced_count += 1

        self.stdout.write(self.style.SUCCESS(f"Synchronized {synced_count} user group memberships."))
        self.stdout.write(self.style.SUCCESS("Dispatch Operation permissions and roles setup complete."))
