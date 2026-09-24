"""
Security, rate limiting, brute-force lockout, and checklist bypass engine for Gametech Unli Fiber.
Protects unified /login/, /portal/login/, and Django /admin/login/.
"""

import sys
import time
import threading
import logging
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# --- Phase 1: Rate Limiting & Account Lockout Engine ---

def get_client_ip(request):
    """
    Extracts the client IP address from X-Forwarded-For or REMOTE_ADDR.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "127.0.0.1")
    return ip


def is_ip_rate_limited(ip, endpoint_name="login", limit=15, window=60):
    """
    Simple IP sliding-window / bucket rate limiting via cache.
    Allows up to `limit` requests within `window` seconds.
    Returns (is_limited: bool, retry_after: int).
    """
    cache_key = f"ratelimit:{endpoint_name}:{ip}"
    current_data = cache.get(cache_key)
    now = int(time.time())

    if current_data is None:
        # First request in window
        cache.set(cache_key, {"count": 1, "start": now}, window)
        return False, 0

    count = current_data.get("count", 0)
    start_time = current_data.get("start", now)
    elapsed = now - start_time

    if elapsed >= window:
        # Window expired, reset
        cache.set(cache_key, {"count": 1, "start": now}, window)
        return False, 0

    if count >= limit:
        retry_after = max(1, window - elapsed)
        return True, retry_after

    # Increment counter
    current_data["count"] = count + 1
    remaining_ttl = max(1, window - elapsed)
    cache.set(cache_key, current_data, remaining_ttl)
    return False, 0


def is_account_or_ip_locked(identifier, ip):
    """
    Checks if this account + IP combination or account is currently locked out.
    Returns (is_locked: bool, remaining_seconds: int).
    """
    clean_id = str(identifier).strip().lower()
    lockout_key = f"lockout:acc_ip:{ip}:{clean_id}"
    lockout_info = cache.get(lockout_key)

    if not lockout_info:
        # Also check pure account lockout
        acc_key = f"lockout:acc:{clean_id}"
        lockout_info = cache.get(acc_key)

    if not lockout_info:
        return False, 0

    lock_until = lockout_info.get("until", 0)
    now = int(time.time())
    if now < lock_until:
        return True, lock_until - now

    # Lock expired, cleanup
    cache.delete(lockout_key)
    return False, 0


def record_login_failure(identifier, ip, max_attempts=5, lock_duration=900):
    """
    Records a failed login attempt. If failed attempts >= max_attempts,
    locks account + IP for `lock_duration` seconds (default 15 minutes = 900s).
    Logs event to SystemLog.
    Returns (is_locked: bool, attempts_count: int, remaining_seconds: int).
    """
    clean_id = str(identifier).strip().lower()
    attempts_key = f"failed_attempts:{ip}:{clean_id}"
    attempts = cache.get(attempts_key, 0) + 1
    cache.set(attempts_key, attempts, lock_duration)

    now = int(time.time())

    if attempts >= max_attempts:
        lock_until = now + lock_duration
        lock_data = {"until": lock_until, "ip": ip, "identifier": clean_id}

        cache.set(f"lockout:acc_ip:{ip}:{clean_id}", lock_data, lock_duration)
        cache.set(f"lockout:acc:{clean_id}", lock_data, lock_duration)

        try:
            from billing.models import SystemLog

            SystemLog.objects.create(
                table_name="Security",
                record_id=0,
                action="ACCOUNT_LOCKED",
                changed_by="SecurityGate",
                target_name=clean_id,
                old_data=f"IP: {ip}",
                new_data=f"Account '{clean_id}' and IP {ip} locked for 15 minutes after {attempts} failed attempts.",
            )
        except Exception:
            pass

        return True, attempts, lock_duration

    try:
        from billing.models import SystemLog

        SystemLog.objects.create(
            table_name="Security",
            record_id=0,
            action="LOGIN_FAILED",
            changed_by="SecurityGate",
            target_name=clean_id,
            old_data=f"IP: {ip}",
            new_data=f"Failed login attempt ({attempts}/{max_attempts}) for '{clean_id}'.",
        )
    except Exception:
        pass

    return False, attempts, 0


def clear_login_failures(identifier, ip):
    """
    Clears failed attempt counters and lockout upon successful authentication.
    """
    clean_id = str(identifier).strip().lower()
    cache.delete(f"failed_attempts:{ip}:{clean_id}")
    cache.delete(f"lockout:acc_ip:{ip}:{clean_id}")
    cache.delete(f"lockout:acc:{clean_id}")


# --- Phase 3.2: Checklist Bypass & Test Seeding Security Controls ---

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
