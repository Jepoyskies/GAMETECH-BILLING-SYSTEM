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
                    
                    # Safely parse if backend returned a string
                    if isinstance(last_seen, str):
                        from django.utils.dateparse import parse_datetime
                        parsed = parse_datetime(last_seen)
                        if parsed:
                            last_seen = parsed
                    
                    # Make aware if naive
                    if last_seen and getattr(last_seen, 'tzinfo', None) is None:
                        last_seen = timezone.make_aware(last_seen)
                        
                    # In case parsing failed and it's still a string
                    if isinstance(last_seen, str):
                        last_seen = None
                    
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
                if isinstance(last_seen, str):
                    from django.utils.dateparse import parse_datetime
                    parsed = parse_datetime(last_seen)
                    if parsed:
                        last_seen = parsed
                    else:
                        last_seen = None
                if last_seen and getattr(last_seen, 'tzinfo', None) is None:
                    last_seen = timezone.make_aware(last_seen)

                if not last_seen or (now - last_seen).total_seconds() > 30:
                    cache.set(cache_key, now, 300)
                    request.session['customer_last_seen'] = now.isoformat()
                    active_customers = cache.get("active_portal_customers") or {}
                    active_customers[str(customer_id)] = now.isoformat()
                    # Clean expired (older than 5 minutes) or logged-out
                    from django.utils.dateparse import parse_datetime
                    cleaned = {}
                    for cid_str, ts_str in list(active_customers.items()):
                        try:
                            # If individual seen key was deleted on logout or expired, exclude it
                            if cache.get(f"seen_customer_{cid_str}") is None:
                                continue
                            ts = parse_datetime(ts_str) if isinstance(ts_str, str) else ts_str
                            if ts and getattr(ts, 'tzinfo', None) is None:
                                ts = timezone.make_aware(ts)
                            if ts and (now - ts).total_seconds() < 300:
                                cleaned[str(cid_str)] = ts_str
                        except Exception:
                            pass
                    cache.set("active_portal_customers", cleaned, 600)
        except Exception:
            pass

        return response
