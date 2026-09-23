from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
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
    available_roles = StaffRole.objects.all().order_by('name')
    return render(
        request, "billing/staff_and_admins.html", {
            "staff_members": staff_members,
            "available_roles": available_roles,
        }
    )


ROLE_MODULE_SPECS = [
    {
        "key": "billing",
        "name": "Billing & CRM",
        "icon": "fa-users",
        "flag": "can_access_billing",
        "subtabs": [
            ("dashboard", "Dashboard", "fa-chart-pie"),
            ("customers", "Customers", "fa-user-friends"),
            ("subscriptions", "Subscriptions", "fa-file-invoice-dollar"),
            ("plans", "Internet Plans", "fa-wifi"),
            ("payments", "Payments", "fa-money-bill-wave"),
            ("payment_logs", "Payment Logs", "fa-receipt"),
        ]
    },
    {
        "key": "network_ops",
        "name": "Network Operations",
        "icon": "fa-network-wired",
        "flag": "can_access_network_ops",
        "subtabs": [
            ("live_monitoring", "Live Monitoring", "fa-heartbeat"),
            ("devices", "Mikrotik Devices", "fa-server"),
            ("active_users", "Active Users", "fa-users-cog"),
            ("geomap", "GeoMap", "fa-map-marked-alt"),
            ("winbox", "Winbox Dashboard", "fa-desktop"),
            ("downdetector", "Downdetector", "fa-bolt"),
            ("speedtest", "Speedtest", "fa-tachometer-alt"),
        ]
    },
    {
        "key": "dispatch",
        "name": "Dispatch System",
        "icon": "fa-truck-fast",
        "flag": "can_access_dispatch",
        "subtabs": [
            ("dispatch_dashboard", "Dashboard", "fa-gauge-high"),
            ("dispatch_operation", "Dispatch Operation / Pipeline", "fa-route"),
            ("dispatch_monitoring", "Master Log", "fa-clipboard-list"),
            ("internet_install", "Internet Install", "fa-plug"),
            ("client_concerns", "Client Concerns", "fa-headset"),
            ("agents", "Agents", "fa-user-tie"),
            ("management", "Management", "fa-sliders"),
            ("audit_log", "Audit Log", "fa-history"),
        ]
    },
    {
        "key": "cignal_play",
        "name": "Cignal Play",
        "icon": "fa-tv",
        "flag": "can_access_cignal_play",
        "subtabs": [
            ("cignal_dashboard", "Dashboard", "fa-tv"),
            ("cignal_applications", "Applications", "fa-file-alt"),
            ("cignal_logs", "Activity Logs", "fa-list-check"),
        ]
    },
    {
        "key": "administration",
        "name": "Administration / Settings",
        "icon": "fa-cogs",
        "flag": "can_access_administration",
        "subtabs": [
            ("logs", "Logs", "fa-scroll"),
            ("settings", "Settings", "fa-cog"),
            ("admin_panel", "Admin Panel", "fa-toolbox"),
            ("improvement_requests", "Improvement Requests", "fa-lightbulb"),
        ]
    },
]


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

        def parse_subtabs(post_data, can_bill, can_net, can_cig, can_disp, can_adm):
            module_flags = {
                "billing": can_bill,
                "network_ops": can_net,
                "cignal_play": can_cig,
                "dispatch": can_disp,
                "administration": can_adm,
            }
            res = {}
            for mod in ROLE_MODULE_SPECS:
                m_key = mod["key"]
                res[m_key] = {}
                is_mod_active = module_flags.get(m_key, False)
                has_subtab_inputs = any(f"subtab_{m_key}_{s[0]}" in post_data for s in mod["subtabs"])
                for s in mod["subtabs"]:
                    s_key = s[0]
                    if not is_mod_active:
                        res[m_key][s_key] = False
                    elif has_subtab_inputs:
                        res[m_key][s_key] = f"subtab_{m_key}_{s_key}" in post_data
                    else:
                        res[m_key][s_key] = True
            return res

        subtab_perms = parse_subtabs(
            request.POST,
            can_access_billing,
            can_access_network_ops,
            can_access_cignal_play,
            can_access_dispatch,
            can_access_administration
        )

        if action == "delete" and role_id:
            role = StaffRole.objects.filter(id=role_id).first()
            if role:
                if role.name.lower() == "admin":
                    messages.error(request, "The core Admin role cannot be deleted.")
                else:
                    role.delete()
                    messages.success(request, f"Role '{role.name}' deleted successfully.")
        elif name:
            if action in ("create", "add"):
                if StaffRole.objects.filter(name__iexact=name).exists():
                    messages.error(request, f"A role named '{name}' already exists.")
                else:
                    StaffRole.objects.create(
                        name=name,
                        can_access_billing=can_access_billing,
                        can_access_network_ops=can_access_network_ops,
                        can_access_cignal_play=can_access_cignal_play,
                        can_access_dispatch=can_access_dispatch,
                        can_access_administration=can_access_administration,
                        subtab_permissions=subtab_perms
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
                        role.subtab_permissions = subtab_perms
                        role.save()
                        messages.success(request, f"Role '{name}' updated successfully.")
        return redirect("manage_roles")

    roles = StaffRole.objects.all().order_by("name")
    for r in roles:
        r.subtabs_data = []
        for mod in ROLE_MODULE_SPECS:
            m_key = mod["key"]
            is_active = getattr(r, mod["flag"], False)
            subs = []
            for s_key, s_name, s_icon in mod["subtabs"]:
                allowed = r.has_subtab_perm(m_key, s_key)
                subs.append({
                    "key": s_key,
                    "name": s_name,
                    "icon": s_icon,
                    "allowed": allowed,
                    "field_name": f"subtab_{m_key}_{s_key}",
                })
            r.subtabs_data.append({
                "key": m_key,
                "name": mod["name"],
                "icon": mod["icon"],
                "flag": mod["flag"],
                "is_active": is_active,
                "subtabs": subs,
                "active_subs_count": sum(1 for s in subs if s["allowed"]),
                "total_subs_count": len(subs),
            })

    return render(request, "billing/manage_roles.html", {
        "roles": roles,
        "module_specs": ROLE_MODULE_SPECS,
    })


@role_required(["Admin"])
@login_required
def add_staff(request):
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.POST.get("is_ajax") == "true"
    available_roles = StaffRole.objects.all().order_by('name')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        role_name = request.POST.get("role", "").strip()
        status = request.POST.get("status", "Active").strip()
        raw_password = request.POST.get("password", "")

        if not username or not full_name or not email or not role_name or not raw_password:
            err_msg = "Please fill in all required fields."
            if is_ajax:
                return JsonResponse({"status": "error", "message": err_msg}, status=400)
            messages.error(request, err_msg)
            return render(request, "billing/add_staff.html", {"available_roles": available_roles, "form_data": request.POST})

        if (
            User.objects.filter(username__iexact=username).exists()
            or SystemAdmin.objects.filter(username__iexact=username).exists()
        ):
            err_msg = "That username is already taken."
            if is_ajax:
                return JsonResponse({"status": "error", "message": err_msg}, status=400)
            messages.error(request, err_msg)
            return render(request, "billing/add_staff.html", {"available_roles": available_roles, "form_data": request.POST})

        if (
            User.objects.filter(email__iexact=email).exists()
            or SystemAdmin.objects.filter(email__iexact=email).exists()
        ):
            err_msg = "That email is already registered."
            if is_ajax:
                return JsonResponse({"status": "error", "message": err_msg}, status=400)
            messages.error(request, err_msg)
            return render(request, "billing/add_staff.html", {"available_roles": available_roles, "form_data": request.POST})

        try:
            with transaction.atomic():
                parts = full_name.split()
                first_name = parts[0] if parts else ""
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

                user = User(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=True,
                    is_active=(status == "Active"),
                )
                if role_name == "Admin":
                    user.is_superuser = True
                user.set_password(raw_password)
                user.save()

                if role_name:
                    group, _ = Group.objects.get_or_create(name=role_name)
                    user.groups.add(group)

                SystemAdmin.objects.create(
                    username=username,
                    full_name=full_name,
                    email=email,
                    role=role_name,
                    status=status,
                    password_hash=make_password(raw_password),
                )

            success_msg = f"Staff member '{full_name}' added successfully!"
            if is_ajax:
                return JsonResponse({"status": "success", "message": success_msg})
            messages.success(request, success_msg)
            return redirect("staff_list")
        except Exception as e:
            err_msg = f"Error creating staff member: {str(e)}"
            if is_ajax:
                return JsonResponse({"status": "error", "message": err_msg}, status=400)
            messages.error(request, err_msg)
            return render(request, "billing/add_staff.html", {"available_roles": available_roles, "form_data": request.POST})

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

    staff = SystemAdmin.objects.filter(pk=pk).first()
    if not staff:
        # Fallback: check if pk is User.id
        user_match = User.objects.filter(pk=pk).first()
        if user_match:
            staff = SystemAdmin.objects.filter(username=user_match.username).first()
            if not staff:
                # Auto-sync missing SystemAdmin profile for this User
                staff = SystemAdmin.objects.create(
                    username=user_match.username,
                    full_name=user_match.get_full_name() or user_match.username,
                    email=user_match.email or "",
                    role="Admin" if user_match.is_superuser else "Standard",
                    status="Active" if user_match.is_active else "Inactive",
                )
    if not staff:
        raise Http404("Staff account not found.")
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
        staff = SystemAdmin.objects.filter(pk=pk).first()
        user = None
        if not staff:
            user = User.objects.filter(pk=pk).first()
            if user:
                staff = SystemAdmin.objects.filter(username=user.username).first()
        if not staff and not user:
            raise Http404("Staff account not found.")

        target_username = staff.username if staff else user.username
        if target_username == request.user.username:
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
