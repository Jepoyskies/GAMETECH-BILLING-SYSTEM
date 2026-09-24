from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from billing.models import Prospect, Customer, SystemAdmin
from dispatch.models import JobTicket


DISPATCH_PERMISSIONS = {
    # billing / prospect permissions
    "submit_prospect": ("Can submit prospect referrals", Prospect),
    "view_own_referrals": ("Can view own referral leads and progress", Prospect),
    "manage_prospects": ("Can view and manage prospect inbox", Prospect),
    "run_checklist": ("Can execute onboarding policy checklist", Prospect),
    "create_customer": ("Can convert prospect and create customer", Prospect),
    "change_agent": ("Can change customer assigned sales agent", Customer),
    "mark_payout_paid": ("Can approve and mark agent payout batches as paid", Customer),
    "manage_message_templates": ("Can configure SMS and notification templates", Customer),
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
        "manage_message_templates",
    ],
    "CSR": [
        "manage_prospects",
        "run_checklist",
        "create_customer",
        "change_agent",
        "manage_message_templates",
    ],
    "Admin": list(DISPATCH_PERMISSIONS.keys()),
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

        # 2. Create Groups and assign permissions
        for role_name, perms in ROLE_PERMISSION_MATRIX.items():
            group, created = Group.objects.get_or_create(name=role_name)
            group_perms = [perm_objs[p] for p in perms if p in perm_objs]
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
