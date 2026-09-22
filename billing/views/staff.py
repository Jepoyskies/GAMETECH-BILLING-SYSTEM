from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from billing.decorators import role_required
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Q, ProtectedError, RestrictedError
from django.core.cache import cache
from billing.models import SystemAdmin, StaffRole


@login_required
def staff_list(request):
    """
    List all staff and system admins with auto-sync from Django auth_user.
    """
    for u in User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)):
        sys_admin, created = SystemAdmin.objects.get_or_create(
            username=u.username,
            defaults={
                "full_name": f"{u.first_name} {u.last_name}".strip() or u.username,
                "email": u.email or f"{u.username}@example.com",
                "role": "Admin" if u.is_superuser else "Viewer",
                "status": "Active" if u.is_active else "Inactive",
                "password_hash": "managed_by_django",
            },
        )
        if not created and u.is_superuser and sys_admin.role != "Admin":
            sys_admin.role = "Admin"
            sys_admin.save(update_fields=["role"])

    staff_members = SystemAdmin.objects.all().order_by("-created_at")
    return render(
        request, "billing/staff_and_admins.html", {"staff_members": staff_members}
    )


@role_required(["Admin"])
@login_required
def manage_roles(request):
    if request.method == "POST":
        action = request.POST.get("action")
        role_id = request.POST.get("role_id")
        name = request.POST.get("name", "").strip()
        can_access_billing = "can_access_billing" in request.POST
        can_access_network_ops = "can_access_network_ops" in request.POST
        can_access_cignal_play = "can_access_cignal_play" in request.POST
        can_access_dispatch = "can_access_dispatch" in request.POST
        can_access_administration = "can_access_administration" in request.POST

        if action == "delete" and role_id:
            role = StaffRole.objects.filter(id=role_id).first()
            if role:
                if role.name.lower() == "admin":
                    messages.error(request, "The core Admin role cannot be deleted.")
                else:
                    role.delete()
                    messages.success(request, f"Role '{role.name}' deleted successfully.")
        elif name:
            if action == "create":
                if StaffRole.objects.filter(name__iexact=name).exists():
                    messages.error(request, f"A role named '{name}' already exists.")
                else:
                    StaffRole.objects.create(
                        name=name,
                        can_access_billing=can_access_billing,
                        can_access_network_ops=can_access_network_ops,
                        can_access_cignal_play=can_access_cignal_play,
                        can_access_dispatch=can_access_dispatch,
                        can_access_administration=can_access_administration
                    )
                    messages.success(request, f"Role '{name}' created successfully.")
            elif action == "edit" and role_id:
                role = StaffRole.objects.filter(id=role_id).first()
                if role:
                    if role.name.lower() == "admin" and name.lower() != "admin":
                        messages.error(request, "Cannot rename the core Admin role.")
                    else:
                        role.name = name
                        role.can_access_billing = can_access_billing
                        role.can_access_network_ops = can_access_network_ops
                        role.can_access_cignal_play = can_access_cignal_play
                        role.can_access_dispatch = can_access_dispatch
                        role.can_access_administration = can_access_administration
                        role.save()
                        messages.success(request, f"Role '{name}' updated successfully.")
        return redirect("manage_roles")

    roles = StaffRole.objects.all().order_by("name")
    return render(request, "billing/manage_roles.html", {"roles": roles})


@role_required(["Admin"])
@login_required
def add_staff(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        role_name = request.POST.get("role")
        status = request.POST.get("status", "Active")
        raw_password = request.POST.get("password")

        if (
            User.objects.filter(username=username).exists()
            or SystemAdmin.objects.filter(username=username).exists()
        ):
            messages.error(request, "That username is already taken.")
            return redirect("add_staff")

        if (
            User.objects.filter(email=email).exists()
            or SystemAdmin.objects.filter(email=email).exists()
        ):
            messages.error(request, "That email is already registered.")
            return redirect("add_staff")

        try:
            with transaction.atomic():
                user = User(
                    username=username,
                    email=email,
                    is_staff=True,
                    is_active=(status == "Active"),
                )
                if role_name == "Admin":
                    user.is_superuser = True
                user.set_password(raw_password)
                user.save()

                group = Group.objects.filter(name=role_name).first()
                if group:
                    user.groups.add(group)

                SystemAdmin.objects.create(
                    username=username,
                    full_name=full_name,
                    email=email,
                    role=role_name,
                    status=status,
                    password_hash=make_password(raw_password),
                )

            messages.success(request, f"Staff member '{full_name}' added successfully!")
            return redirect("staff_list")
        except Exception as e:
            messages.error(request, f"Error creating staff member: {str(e)}")
            return redirect("add_staff")

    available_roles = StaffRole.objects.all().order_by('name')
    return render(request, "billing/add_staff.html", {"available_roles": available_roles})


@role_required(["Admin"])
@login_required
def edit_staff(request, pk):
    user_role = getattr(request.user, "role", "Viewer")
    if user_role == "Viewer":
        messages.error(
            request, "Access denied. Viewers are not permitted to edit staff details."
        )
        return redirect("staff_list")

    staff = get_object_or_404(SystemAdmin, pk=pk)
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role")
        status = request.POST.get("status")
        raw_password = request.POST.get("password")

        if (
            User.objects.filter(username=username)
            .exclude(username=staff.username)
            .exists()
            or SystemAdmin.objects.filter(username=username).exclude(pk=pk).exists()
        ):
            messages.error(request, "That username is already taken.")
            return redirect("edit_staff", pk=pk)

        if (
            User.objects.filter(email=email).exclude(email=staff.email).exists()
            or SystemAdmin.objects.filter(email=email).exclude(pk=pk).exists()
        ):
            messages.error(request, "That email is already registered.")
            return redirect("edit_staff", pk=pk)

        try:
            with transaction.atomic():
                user = User.objects.filter(username=staff.username).first()
                if user:
                    user.username = username
                    user.email = email
                    user.is_active = status == "Active"
                    if user_role == "Admin" and raw_password:
                        user.set_password(raw_password)
                    if role == "Admin":
                        user.is_superuser = True
                    else:
                        user.is_superuser = False
                    user.save()

                    if role:
                        group = Group.objects.filter(name=role).first()
                        if group:
                            user.groups.clear()
                            user.groups.add(group)

                staff.username = username
                staff.full_name = full_name
                staff.email = email
                staff.role = role
                staff.status = status

                if user_role == "Admin" and raw_password:
                    if user:
                        staff.password_hash = user.password
                    else:
                        staff.password_hash = make_password(raw_password)

                staff.save()

            messages.success(
                request, f"Staff member '{full_name}' updated successfully!"
            )
            return redirect("staff_list")
        except Exception as e:
            messages.error(request, f"Error updating staff member: {str(e)}")
            return redirect("edit_staff", pk=pk)

    return render(request, "billing/edit_staff.html", {"staff": staff})


@role_required(["Admin"])
@login_required
def delete_staff(request, pk):
    """
    Deletes or deactivates a staff member and their corresponding Django User.
    Guards against self-deletion and gracefully handles restricted foreign keys.
    """
    if request.method == "POST":
        staff = get_object_or_404(SystemAdmin, pk=pk)

        if staff.username == request.user.username:
            messages.error(request, "You cannot delete your own logged-in account.")
            return redirect("staff_list")

        from dispatch.models import Technician

        try:
            with transaction.atomic():
                user = User.objects.filter(username=staff.username).first()
                if user:
                    # Detach technician FK if linked
                    Technician.objects.filter(user=user).update(user=None)

                    # Invalidate session cache
                    cache.delete(f"seen_user_{user.id}")

                    # Attempt deleting Django User
                    try:
                        user.delete()
                    except (ProtectedError, RestrictedError):
                        # If referenced by dispatch/monitoring FKs (RESTRICT), revoke staff privileges
                        user.is_staff = False
                        user.is_active = False
                        user.save(update_fields=["is_staff", "is_active"])

                staff.delete()

            messages.success(request, f"Staff member '{staff.full_name}' ({staff.username}) was deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error deleting staff member: {str(e)}")

    return redirect("staff_list")
