import sys
import threading
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_BYPASS_STATE = threading.local()


class test_seeding_bypass_checklist:
    """
    Context manager allowing test runners and management command seeders
    to bypass the onboarding checklist guard.
    STRICT SECURITY RULE: Works ONLY under settings.DEBUG=True or active test runner.
    Never works on production with DEBUG=False.
    """

    def __init__(self, command_name: str = "test_command"):
        self.command_name = command_name

    def __enter__(self):
        is_testing = (
            getattr(settings, "TESTING", False)
            or "test" in sys.argv
            or any("pytest" in str(arg) for arg in sys.argv)
        )
        if not (settings.DEBUG or is_testing):
            raise PermissionError(
                f"test_seeding_bypass_checklist cannot run when DEBUG=False in production! (Attempted by: {self.command_name})"
            )
        _BYPASS_STATE.test_seeding = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _BYPASS_STATE.test_seeding = False


class permission_gated_customer_bypass:
    """
    Narrow, logged, permission-gated bypass for administrative/legacy import operations.
    Requires an active user with 'billing.bypass_customer_checklist' permission or superuser.
    Logs every use to SystemLog with username, reason, and timestamp.
    """

    def __init__(self, user, reason: str):
        self.user = user
        self.reason = reason

    def __enter__(self):
        if not self.user:
            raise PermissionError("Bypass requires an authenticated administrative user.")
        has_perm = (
            getattr(self.user, "is_superuser", False)
            or getattr(self.user, "has_perm", lambda p: False)(
                "billing.bypass_customer_checklist"
            )
        )
        if not has_perm:
            raise PermissionError(
                f"User '{self.user}' lacks 'billing.bypass_customer_checklist' permission."
            )
        _BYPASS_STATE.admin_bypass = True
        _BYPASS_STATE.admin_user = self.user
        _BYPASS_STATE.admin_reason = self.reason
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        username = getattr(self.user, "username", str(self.user))
        try:
            from billing.models import SystemLog

            SystemLog.objects.create(
                table_name="Customer",
                record_id="0",
                action="SECURITY_BYPASS",
                changed_by=username,
                target_name="ChecklistGuardBypass",
                old_data="",
                new_data=f"Admin checklist bypass exercised by {username}. Reason: {self.reason}",
            )
        except Exception as e:
            logger.error(f"Failed to record SystemLog for checklist bypass: {e}")

        _BYPASS_STATE.admin_bypass = False
        _BYPASS_STATE.admin_user = None
        _BYPASS_STATE.admin_reason = None


def is_checklist_bypass_active() -> bool:
    """Checks whether a valid, authorized bypass is currently active on the thread."""
    if getattr(_BYPASS_STATE, "test_seeding", False):
        is_testing = (
            getattr(settings, "TESTING", False)
            or "test" in sys.argv
            or any("pytest" in str(arg) for arg in sys.argv)
        )
        if settings.DEBUG or is_testing:
            return True
    if getattr(_BYPASS_STATE, "admin_bypass", False):
        return True
    return False
