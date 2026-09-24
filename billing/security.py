"""
Security, rate limiting, and brute-force lockout engine for Gametech Unli Fiber.
Protects unified /login/, /portal/login/, and Django /admin/login/.
"""

import time
from django.core.cache import cache
from django.utils import timezone


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
    from billing.models import SystemLog

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
