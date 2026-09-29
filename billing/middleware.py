import threading

from django.core.cache import cache
from django.utils import timezone

_thread_locals = threading.local()


def get_current_user():
    return getattr(_thread_locals, "user", None)


class ThreadLocalUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, "user", None)
        response = self.get_response(request)
        _thread_locals.user = None
        return response


class ActiveUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Ignore background polling endpoints to prevent artificial activity tracking
            if (
                not request.path.startswith("/api/")
                and "/network/health/" not in request.path
            ):
                if getattr(request.user, "is_staff", False) or getattr(
                    request.user, "role", None
                ) in ["Admin", "Technician", "CSR"]:
                    cache_key = f"seen_user_{request.user.id}"
                    last_seen = cache.get(cache_key)
                    now = timezone.now()

                    if not last_seen or (now - last_seen).total_seconds() > 60:
                        cache.set(cache_key, now, 60 * 60 * 24 * 30)  # 30 days

        response = self.get_response(request)

        # Track active Customer Portal subscriber sessions
        try:
            customer_id = request.session.get("customer_id")
            if customer_id and not request.path.startswith("/static/"):
                now = timezone.now()
                cache_key = f"seen_customer_{customer_id}"
                last_seen = cache.get(cache_key)

                if not last_seen or (now - last_seen).total_seconds() > 30:
                    cache.set(cache_key, now, 300)
                    request.session["customer_last_seen"] = now.isoformat()
                    # Lightweight active customer tracking — just set, cleanup happens on logout
                    cache.set(f"active_portal_customer_{customer_id}", now.isoformat(), 600)
        except Exception:
            pass

        return response


class LoginRateLimitMiddleware:
    """
    IP rate limiting on authentication POST requests to prevent brute-force attacks.
    Applies to /login/, /portal/login/, and /admin/login/.
    """
    RATE_LIMITED_PATHS = ("/login/", "/portal/login/", "/admin/login/", "/admin/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and any(request.path.startswith(p) for p in self.RATE_LIMITED_PATHS):
            from billing.security import get_client_ip, is_ip_rate_limited
            from django.http import HttpResponse

            ip = get_client_ip(request)
            is_limited, retry_after = is_ip_rate_limited(ip, endpoint_name="auth_post", limit=15, window=60)
            if is_limited:
                resp = HttpResponse(
                    f"Too many login attempts from your IP ({ip}). Please wait {retry_after} seconds.",
                    status=429,
                    content_type="text/plain",
                )
                resp["Retry-After"] = str(retry_after)
                return resp

        return self.get_response(request)

