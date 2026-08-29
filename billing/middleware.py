import threading

from django.core.cache import cache
from django.utils import timezone

_thread_locals = threading.local()

def get_current_user():
    return getattr(_thread_locals, 'user', None)

class ThreadLocalUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        response = self.get_response(request)
        _thread_locals.user = None
        return response

class ActiveUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if getattr(request.user, 'is_staff', False) or getattr(request.user, 'role', None) in ['Admin', 'Technician', 'CSR']:
                cache_key = f'seen_user_{request.user.id}'
                last_seen = cache.get(cache_key)
                now = timezone.now()
                if not last_seen or (now - last_seen).total_seconds() > 60:
                    cache.set(cache_key, now, 60*60*24*30) # 30 days

        response = self.get_response(request)
        return response
