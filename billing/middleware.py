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
                cache.set(cache_key, timezone.now(), 300) # Expire in 5 minutes
                
        response = self.get_response(request)
        return response
