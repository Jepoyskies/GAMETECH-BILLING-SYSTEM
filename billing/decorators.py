from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.shortcuts import redirect

def role_required(allowed_roles):
    """
    Decorator for views that checks that the user's role is in the allowed_roles list.
    If not, it redirects to the dashboard with an error message, or raises PermissionDenied.
    """
    def check_role(user):
        if not user.is_authenticated:
            return False
        user_role = getattr(user, 'role', 'Viewer')
        return user_role in allowed_roles

    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if check_role(request.user):
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "You do not have permission to access this page or perform this action.")
                # To prevent redirect loops if they are already on the dashboard, we can just redirect to dashboard
                # but if the dashboard is protected (it shouldn't be), we are safe.
                # Actually, maybe better to redirect to HTTP_REFERER if available
                referer = request.META.get('HTTP_REFERER')
                if referer and request.build_absolute_uri() != referer:
                    return redirect(referer)
                return redirect('dashboard')
        return _wrapped_view
    return decorator
