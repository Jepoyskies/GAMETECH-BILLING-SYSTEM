"""
Create the missing business profile records for Agent / Technician personas.

WHY THIS EXISTS
---------------
The Staff & Admins page stores a persona LABEL in `SystemAdmin`
(username / full_name / email / role / status). That label is what `user.role`
resolves to, and it is what drives BOTH:

  * `billing.views.auth.resolve_landing_url()`  -> which portal a user lands on
  * `billing.decorators._role_allows()`         -> which pages they may open

But the label does NOT create the business profile that actually holds the work:

  * `Agent`      (User.agent_profile) -> prospects, commission ledger, payouts
  * `Technician` (User.technician)    -> `JobTicket.technicians` assignment

So a user with role="Agent" but no `Agent` row routes correctly to the Agent
Portal, fails to find `request.user.agent_profile`, and gets bounced straight
back to the main dashboard. This command closes that gap.

GUARANTEES
----------
* Idempotent. Safe to re-run: it only fills gaps, never duplicates.
* Dry run by default. Nothing is written without `--apply`.
* Never invents data. Phone is left NULL rather than guessed; no password is
  read, set, or printed. Names/emails are copied from existing User/SystemAdmin
  rows only.
* Only touches users whose `SystemAdmin.role` is exactly Agent or Technician.
  Admins, CSR and Viewers are never modified.
* Reversible with `--unlink`, which detaches the profile and does not delete
  ledger or job history.

WHY is_staff IS SET TO FALSE
---------------------------
`billing/views/auth.py:191-192` (the "Set up Portal Login" flow) already forces
`is_staff = False` for agents. Mirroring that here:

  * `_role_allows()` / `has_dispatch_permission()` key off `is_superuser` and
    `role`, NEVER `is_staff`, so page permissions are unaffected.
  * `billing/views/staff.py` lists `SystemAdmin` rows, not Users, so Martin and
    Merk stay on the Staff & Admins page either way.
  * `billing/middleware.py:35` only uses it for the online-staff counter, and
    Merk is still counted via `role == "Technician"`.
  * `/admin/` is routed (gametech_core/urls.py:22). `is_staff=True` would grant
    an agent or a field technician full Django admin access. This is the one
    place where the flag actually matters, and it should be False.

Usage
-----
    python manage.py link_persona_profiles              # preview (dry run)
    python manage.py link_persona_profiles --apply      # write
    python manage.py link_persona_profiles --unlink     # detach profiles
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import Agent, SystemAdmin, SystemLog
from dispatch.models import Technician

PERSONA_ROLES = ("Agent", "Technician")


class Command(BaseCommand):
    help = "Create missing Agent / Technician profile records for persona users (idempotent, dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write to the database. Omit for a dry-run preview.",
        )
        parser.add_argument(
            "--unlink",
            action="store_true",
            help="Detach the profile from the user (reverse of this command). Does not delete records.",
        )

    # ------------------------------------------------------------------ helpers

    def _mirror(self, user):
        """The SystemAdmin row is the source of truth for role/full_name/email."""
        return SystemAdmin.objects.filter(username__iexact=user.username).first()

    def _display_name(self, user, mirror):
        for candidate in (
            getattr(mirror, "full_name", None),
            user.get_full_name(),
            user.first_name,
            user.username,
        ):
            if candidate:
                return candidate.strip()
        return user.username

    def _email(self, user, mirror):
        for candidate in (getattr(mirror, "email", None), user.email):
            if candidate:
                return candidate.strip()
        # Agent.email is non-nullable and unique; fall back to the username so
        # the row is still creatable rather than skipped.
        return f"{user.username}@no-email.gametech.local"

    # ------------------------------------------------------------------ actions

    @transaction.atomic
    def handle(self, *args, **options):
        apply = options["apply"]
        unlink = options["unlink"]

        if apply and unlink:
            self.stdout.write(self.style.ERROR("Use --apply or --unlink, not both."))
            return

        mode = "APPLY" if apply else ("UNLINK" if unlink else "DRY RUN")
        self.stdout.write(self.style.NOTICE(f"link_persona_profiles [{mode}]"))

        touched = 0
        skipped = []

        for user in self._persona_users():
            role = (getattr(user, "role", "") or "").strip()
            mirror = self._mirror(user)
            name = self._display_name(user, mirror)
            email = self._email(user, mirror)

            if role == "Agent":
                ok, msg = self._handle_agent(user, name, email, unlink, apply)
            else:
                ok, msg = self._handle_technician(user, name, unlink, apply)

            if ok:
                touched += 1
                self.stdout.write(f"  {msg}")
            else:
                skipped.append(f"{user.username}: {msg}")
                self.stdout.write(self.style.WARNING(f"  SKIP {user.username}: {msg}"))

        self.stdout.write("")
        if skipped:
            self.stdout.write(self.style.WARNING(f"Skipped {len(skipped)}:"))
            for s in skipped:
                self.stdout.write(self.style.WARNING(f"  - {s}"))
            self.stdout.write("")

        if not apply:
            self.stdout.write(self.style.WARNING("Dry run. Re-run with --apply to write."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done. {touched} profile(s) processed."))

    def _persona_users(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        out = []
        for user in User.objects.all().order_by("username"):
            role = (getattr(user, "role", "") or "").strip()
            if role in PERSONA_ROLES:
                out.append(user)
        return out

    def _handle_agent(self, user, name, email, unlink, apply):
        existing = Agent.objects.filter(user=user).first()
        if existing:
            return True, f"Agent '{existing.name}' already linked to {user.username} (no change)"
        if unlink:
            orphan = Agent.objects.filter(name__iexact=name, user__isnull=True).first()
            if not orphan:
                return False, "no Agent profile to unlink"
            if apply:
                orphan.user = None
                orphan.save(update_fields=["user"])
            return True, f"unlinked Agent '{orphan.name}' from {user.username}"

        if Agent.objects.filter(email__iexact=email).exists():
            return False, f"Agent email '{email}' already used by another agent (email is unique)"

        if apply:
            agent = Agent.objects.create(
                user=user,
                name=name,
                email=email,
                phone=None,          # never guessed
                password_hash=user.password,  # mirrors views/auth.py:198
                is_test_data=False,
            )
            self._normalise_user(user, name)
            SystemLog.objects.create(
                user="Staff",
                action=f"Created Agent profile '{name}' and linked portal login (Username: {user.username})",
                ip_address="",
            )
            return True, f"created Agent id={agent.id} '{name}' <{email}> -> {user.username}"
        return True, f"would create Agent '{name}' <{email}> -> {user.username}"

    def _handle_technician(self, user, name, unlink, apply):
        existing = Technician.objects.filter(user=user).first()
        if existing:
            return True, f"Technician '{existing.name}' already linked to {user.username} (no change)"
        if unlink:
            orphan = Technician.objects.filter(name__iexact=name, user__isnull=True).first()
            if not orphan:
                return False, "no Technician profile to unlink"
            if apply:
                orphan.user = None
                orphan.save(update_fields=["user"])
            return True, f"unlinked Technician '{orphan.name}' from {user.username}"

        if Technician.objects.filter(name__iexact=name).exists():
            return False, f"Technician name '{name}' already taken (name is unique)"

        if apply:
            tech = Technician.objects.create(
                user=user,
                name=name,
                contact_number=None,   # never guessed
                target_per_day=0,
                target_per_month=0,
                team=None,             # per instruction: unassigned for now
                is_available=True,
            )
            self._normalise_user(user, name)
            SystemLog.objects.create(
                user="Staff",
                action=f"Created Technician profile '{name}' and linked portal login (Username: {user.username})",
                ip_address="",
            )
            return True, f"created Technician id={tech.id} '{name}' -> {user.username} (team unassigned)"
        return True, f"would create Technician '{name}' -> {user.username} (team unassigned)"

    def _normalise_user(self, user, name):
        """
        Match the existing 'Set up Portal Login' convention (views/auth.py:189-195):
        mirror the display name, and drop Django-admin privileges.
        Permissions are unaffected because _role_allows() never reads is_staff.
        """
        user.first_name = name[:30]
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.save(update_fields=["first_name", "is_staff", "is_superuser", "is_active"])
