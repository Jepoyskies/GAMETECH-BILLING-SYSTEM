from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.shortcuts import redirect


from django.http import JsonResponse


def role_required(allowed_roles):
    """
    Decorator for views that checks that the user's role is in the allowed_roles list.
    If not, it redirects to the dashboard with an error message, or raises PermissionDenied.
    """

    def check_role(user):
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True  # Superusers pass all role checks

        user_role = getattr(user, "role", None)
        if not user_role or user_role == "Viewer":
            from billing.models import SystemAdmin
            admin = SystemAdmin.objects.filter(username__iexact=user.username).first()
            if admin:
                user_role = admin.role

        if user_role and user_role in allowed_roles:
            return True

        if "Admin" in allowed_roles:
            role_perms = getattr(user, "role_perms", None)
            if role_perms and (
                getattr(role_perms, "can_access_administration", False)
                or (hasattr(role_perms, "has_subtab_perm") and role_perms.has_subtab_perm("administration", "admin_panel"))
            ):
                return True

        return False

    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "error", "message": "Authentication required."}, status=401)
                return redirect("login")
            if check_role(request.user):
                return view_func(request, *args, **kwargs)
            else:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "error", "message": "You do not have permission to perform this action."}, status=403)
                messages.error(
                    request,
                    "You do not have permission to access this page or perform this action.",
                )
                referer = request.META.get("HTTP_REFERER")
                if referer and request.build_absolute_uri() != referer:
                    return redirect(referer)
                return redirect("dashboard")

        return _wrapped_view

    return decorator
