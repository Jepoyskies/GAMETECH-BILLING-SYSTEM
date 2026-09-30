from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.shortcuts import redirect


from django.http import JsonResponse


def module_required(module, subtab=None, extra_roles=None):
    """
    MATRIX-DRIVEN ACCESS — the "Edit Roles" screen actually enforces views.

    Grants access when the user's StaffRole grants `module` (and, when
    `subtab` is given, that specific subtab). This is the decorator that
    makes the role editor authoritative instead of cosmetic.

        @module_required("dispatch", "agents")
        def agent_list(request): ...

    `extra_roles` keeps an explicit allow-list escape hatch, e.g.
    module_required("administration", "admin_panel", ["Admin"]).
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "error", "message": "Authentication required."}, status=401)
                return redirect("login")

            if _module_allows(user, module, subtab, extra_roles):
                return view_func(request, *args, **kwargs)

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"status": "error", "message": "You do not have permission to perform this action."},
                    status=403,
                )
            messages.error(request, "You do not have permission to access this page or perform this action.")
            referer = request.META.get("HTTP_REFERER")
            if referer and request.build_absolute_uri() != referer:
                return redirect(referer)
            return redirect("dashboard")
        return _wrapped_view
    return decorator


def action_required(module, action, subtab=None, extra_roles=None):
    """
    ACTION-LEVEL GATE — "view agents but not create agents".

    Reads the `_actions` block inside StaffRole.subtab_permissions.
    When a role has no `_actions` block configured it falls back to the
    subtab grant, so existing roles keep working untouched.

        @action_required("dispatch", "create", subtab="agents")
        def add_agent(request): ...
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "error", "message": "Authentication required."}, status=401)
                return redirect("login")

            if _action_allows(user, module, action, subtab, extra_roles):
                return view_func(request, *args, **kwargs)

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"status": "error",
                     "message": f"You do not have permission to {action} in this area."},
                    status=403,
                )
            messages.error(request, f"You do not have permission to {action} in this area.")
            referer = request.META.get("HTTP_REFERER")
            if referer and request.build_absolute_uri() != referer:
                return redirect(referer)
            return redirect("dashboard")
        return _wrapped_view
    return decorator


def _action_allows(user, module, action, subtab=None, extra_roles=None):
    """Shared check behind @action_required."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    user_role = getattr(user, "role", None)
    if not user_role:
        from billing.models import SystemAdmin
        admin = SystemAdmin.objects.filter(username__iexact=user.username).first()
        user_role = admin.role if admin else None

    if extra_roles and user_role and user_role in extra_roles:
        return True

    role_perms = getattr(user, "role_perms", None)
    if role_perms is None:
        return False

    if not getattr(role_perms, f"can_access_{module}", False):
        return False

    if subtab and not role_perms.has_subtab_perm(module, subtab):
        return False

    if hasattr(role_perms, "get_action_perm"):
        return bool(role_perms.get_action_perm(module, action, fallback=True))
    return True


def _module_allows(user, module, subtab=None, extra_roles=None):
    """Shared check behind @module_required."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    user_role = getattr(user, "role", None)
    if not user_role:
        from billing.models import SystemAdmin
        admin = SystemAdmin.objects.filter(username__iexact=user.username).first()
        user_role = admin.role if admin else None

    if extra_roles and user_role and user_role in extra_roles:
        return True

    role_perms = getattr(user, "role_perms", None)
    if role_perms is None:
        return False

    if not getattr(role_perms, f"can_access_{module}", False):
        return False

    if subtab:
        return bool(role_perms.has_subtab_perm(module, subtab))
    return True


def _role_allows(user, allowed_roles):
    """
    THE ONE ROLE GATE (Rule: single source of truth).

    Resolution order:
      1. Superuser                      -> always allowed
      2. Role name in allowed_roles     -> allowed (explicit allow-list)
      3. Role matrix from StaffRole     -> allowed when the role's own
         (the "Edit Roles" UI data)        module/subtab grants the module.

    Step 3 is what makes the Edit Roles screen actually enforce access.
    Before this, role_required only compared role NAMES, so ticking a
    subtab in the UI changed the sidebar but not the view.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    user_role = getattr(user, "role", None)
    if not user_role:
        from billing.models import SystemAdmin
        admin = SystemAdmin.objects.filter(username__iexact=user.username).first()
        user_role = admin.role if admin else None

    if user_role and user_role in allowed_roles:
        return True

    # "Admin" in the allow-list keeps its historical extra path: anyone whose
    # role grants the Administration module may reach admin pages.
    if "Admin" in allowed_roles:
        role_perms = getattr(user, "role_perms", None)
        if role_perms and (
            getattr(role_perms, "can_access_administration", False)
            or (hasattr(role_perms, "has_subtab_perm")
                and role_perms.has_subtab_perm("administration", "admin_panel"))
        ):
            return True

    return False


def role_required(allowed_roles):
    """
    Decorator for views that checks that the user's role is in the allowed_roles list.
    If not, it redirects to the dashboard with an error message, or raises PermissionDenied.
    """
    def check_role(user):
        return _role_allows(user, allowed_roles)

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


def has_dispatch_permission(user, perm_codename):
    """
    Checks if a user has a specific dispatch or billing operation permission.
    Supports:
    1. Superuser / Admin role -> always True
    2. Direct Django permission (billing.<codename> or dispatch.<codename>)
    3. Group-based permission (User is in Group that has this permission)
    4. Role matrix fallback
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    user_role = getattr(user, "role", None)
    if not user_role:
        from billing.models import SystemAdmin
        admin = SystemAdmin.objects.filter(username__iexact=user.username).first()
        if admin:
            user_role = admin.role

    if user_role == "Admin":
        return True

    # Check standard Django permissions (direct and through Groups)
    if user.has_perm(f"billing.{perm_codename}") or user.has_perm(f"dispatch.{perm_codename}"):
        return True

    # Fallback to role matrix
    try:
        from billing.management.commands.setup_dispatch_permissions import ROLE_PERMISSION_MATRIX
        allowed_perms = ROLE_PERMISSION_MATRIX.get(user_role, [])
        return perm_codename in allowed_perms
    except Exception:
        return False


def dispatch_permission_required(perm_codename):
    """
    View decorator that verifies the authenticated user holds the required dispatch permission.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "error", "message": "Authentication required."}, status=401)
                return redirect("login")
            if has_dispatch_permission(request.user, perm_codename):
                return view_func(request, *args, **kwargs)
            else:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {"status": "error", "message": f"Permission denied. Required permission: '{perm_codename}'."},
                        status=403,
                    )
                messages.error(
                    request,
                    f"You do not have the required permission ({perm_codename}) to access this page or action.",
                )
                referer = request.META.get("HTTP_REFERER")
                if referer and request.build_absolute_uri() != referer:
                    return redirect(referer)
                return redirect("dashboard")
        return _wrapped_view
    return decorator

