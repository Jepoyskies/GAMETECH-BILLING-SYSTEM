"""
Unified Sync Manager — shows all routers in one page with their customers,
matching pairs, missing/orphaned PPPoE users, and push/delete functionality.
"""
import json
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from billing.models import Customer, SystemLog, MikrotikDevice
from network_manager.sync_services import MikrotikAPI
from network_manager.sync_helpers import (
    build_router_comment,
    desired_profile,
    mark_synced,
)


@login_required
def sync_manager_view(request):
    """Unified sync manager showing all routers and their sync status."""
    from billing.decorators import role_required

    # Only Admin and Editor can access
    user_role = getattr(request.user, "role", "")
    if user_role not in ("Admin", "Editor") and not request.user.is_superuser:
        messages.error(request, "Access denied. Only Admins and Editors can access the Sync Manager.")
        return redirect("dashboard")

    # Get all routers
    routers = MikrotikDevice.objects.all().order_by("device_name")

    # Build router data with customers and sync status
    router_data = []
    for router in routers:
        # Get customers assigned to this router
        customers = Customer.objects.filter(
            mikrotik_device=router,
            pppoe_username__isnull=False,
        ).exclude(pppoe_username="").select_related("plan", "barangay")

        # Try to get router PPPoE users
        router_users = []
        router_error = None
        try:
            api = MikrotikAPI(
                ip_address=router.ip_address,
                username=router.api_username,
                password=router.api_password,
                port=router.api_port,
            )
            result = api.get_all_pppoe_users()
            if result.get("success"):
                router_users = result.get("data", [])
            else:
                router_error = result.get("error", "Unknown error")
        except Exception as e:
            router_error = str(e)

        # Build matching pairs
        router_usernames = {u.get("name"): u for u in router_users if u.get("name")}
        system_usernames = {c.pppoe_username: c for c in customers if c.pppoe_username}

        matching_pairs = []
        missing_in_router = []
        orphans_in_router = []

        for username, customer in system_usernames.items():
            if username in router_usernames:
                # Matching pair
                router_user = router_usernames[username]
                is_unpaid = customer.status in ("expired", "inactive")
                is_no_expiry = customer.expires_at is None
                matching_pairs.append({
                    "customer": customer,
                    "router_user": router_user,
                    "is_unpaid": is_unpaid,
                    "is_no_expiry": is_no_expiry,
                    "profile_match": router_user.get("profile") == desired_profile(customer),
                })
            else:
                # In system but not in router
                missing_in_router.append(customer)

        for username, router_user in router_usernames.items():
            if username not in system_usernames:
                # In router but not in system
                orphans_in_router.append({
                    "username": username,
                    "router_user": router_user,
                })

        # Determine router status
        router_down = bool(cache.get(f"router_unreachable_{router.id}"))
        if router_down:
            router_status = "Unreachable"
        elif router_error:
            router_status = "Error"
        else:
            router_status = "Online"

        router_data.append({
            "router": router,
            "customers": customers,
            "router_users": router_users,
            "router_error": router_error,
            "router_status": router_status,
            "matching_pairs": matching_pairs,
            "missing_in_router": missing_in_router,
            "orphans_in_router": orphans_in_router,
            "total_customers": len(customers),
            "total_router_users": len(router_users),
            "match_count": len(matching_pairs),
            "missing_count": len(missing_in_router),
            "orphan_count": len(orphans_in_router),
        })

    # Handle push/delete actions
    if request.method == "POST":
        action = request.POST.get("action")
        customer_id = request.POST.get("customer_id")
        router_id = request.POST.get("router_id")

        if action == "push" and customer_id and router_id:
            return _handle_push(request, customer_id, router_id)
        elif action == "delete" and router_id:
            username = request.POST.get("username")
            return _handle_delete(request, router_id, username)
        elif action == "override" and customer_id and router_id:
            return _handle_override(request, customer_id, router_id)

    context = {
        "router_data": router_data,
        "total_routers": len(router_data),
        "total_customers": sum(r["total_customers"] for r in router_data),
        "total_matches": sum(r["match_count"] for r in router_data),
        "total_missing": sum(r["missing_count"] for r in router_data),
        "total_orphans": sum(r["orphan_count"] for r in router_data),
    }

    return render(request, "billing/sync_manager.html", context)


def _handle_push(request, customer_id, router_id):
    """Handle pushing a customer to a router."""
    customer = get_object_or_404(Customer, id=customer_id)
    router = get_object_or_404(MikrotikDevice, id=router_id)

    # Check if customer is unpaid
    if customer.status in ("expired", "inactive"):
        messages.error(
            request,
            f"Cannot push {customer.full_name}: Account is {customer.status}. Admin override required."
        )
        return redirect("sync_manager")

    # Check if customer has no expiration
    if not customer.expires_at:
        messages.error(
            request,
            f"Cannot push {customer.full_name}: No expiration date set. Admin override required."
        )
        return redirect("sync_manager")

    # Push to router
    try:
        api = MikrotikAPI(
            ip_address=router.ip_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port,
        )
        result = api.add_pppoe_user(
            name=customer.pppoe_username,
            password=customer.pppoe_password,
            profile=desired_profile(customer),
            comment=build_router_comment(customer),
        )
        if result.get("success"):
            mark_synced(customer, router, request.user)
            messages.success(request, f"Successfully pushed {customer.full_name} to {router.device_name}.")
        else:
            messages.error(request, f"Failed to push {customer.full_name}: {result.get('error')}")
    except Exception as e:
        messages.error(request, f"Error pushing {customer.full_name}: {str(e)}")

    return redirect("sync_manager")


def _handle_delete(request, router_id, username):
    """Handle deleting an orphan from a router."""
    router = get_object_or_404(MikrotikDevice, id=router_id)

    if not username:
        messages.error(request, "No username specified for deletion.")
        return redirect("sync_manager")

    try:
        api = MikrotikAPI(
            ip_address=router.ip_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port,
        )
        result = api.delete_pppoe_user(username)
        if result.get("success"):
            # Log the deletion
            SystemLog.objects.create(
                table_name="Customer",
                record_id="",
                action="ROUTER_DELETE",
                changed_by=request.user.username,
                target_name=username,
                old_data=f"Orphan on {router.device_name}",
                new_data=f"Deleted by {request.user.username} from Sync Manager",
            )
            messages.success(request, f"Successfully deleted {username} from {router.device_name}.")
        else:
            messages.error(request, f"Failed to delete {username}: {result.get('error')}")
    except Exception as e:
        messages.error(request, f"Error deleting {username}: {str(e)}")

    return redirect("sync_manager")


def _handle_override(request, customer_id, router_id):
    """Handle admin override for pushing unpaid/no-expiry customers."""
    customer = get_object_or_404(Customer, id=customer_id)
    router = get_object_or_404(MikrotikDevice, id=router_id)

    # Verify the OVERRIDING ADMIN's password.
    #
    # This must not fall back to request.user: a CSR pressing "Sync" is
    # exactly the person being blocked, so accepting their own password would
    # make the gate a no-op. An Admin must authenticate by username here.
    admin_username = (request.POST.get("admin_username") or "").strip()
    admin_password = request.POST.get("admin_password") or ""

    admin_user = None
    if admin_username:
        from django.contrib.auth import get_user_model
        admin_user = get_user_model().objects.filter(
            username__iexact=admin_username, is_active=True
        ).first()

    if admin_user is None or not check_password(admin_password, admin_user.password):
        messages.error(
            request,
            f"Override denied: '{admin_username}' is not a valid Admin account, "
            "or the password is incorrect.",
        )
        return redirect("sync_manager")

    # Password is only half the gate. The account must actually be an Admin,
    # otherwise any staff login could be used to wave through unpaid accounts.
    if not (admin_user.is_superuser or getattr(admin_user, "role", "") == "Admin"):
        messages.error(
            request,
            f"Override denied: {admin_user.username} is not an Admin.",
        )
        return redirect("sync_manager")

    # Determine reason
    reasons = []
    if customer.status in ("expired", "inactive"):
        reasons.append(f"Account status: {customer.status}")
    if not customer.expires_at:
        reasons.append("No expiration date")

    # Push to router with override
    try:
        api = MikrotikAPI(
            ip_address=router.ip_address,
            username=router.api_username,
            password=router.api_password,
            port=router.api_port,
        )
        result = api.add_pppoe_user(
            name=customer.pppoe_username,
            password=customer.pppoe_password,
            profile=desired_profile(customer),
            comment=build_router_comment(customer),
        )
        if result.get("success"):
            mark_synced(customer, router, request.user)

            # Audit trail. Records the operator, the approving Admin, the
            # reason, and the exact credentials written, so a disputed
            # connection can be traced back to a person.
            SystemLog.objects.create(
                table_name="Customer",
                record_id=str(customer.id),
                action="SYNC_ADMIN_OVERRIDE",
                changed_by=request.user.username,
                target_name=customer.full_name,
                old_data=(
                    f"status={customer.status}, expires_at={customer.expires_at or 'NONE'}"
                ),
                new_data=(
                    f"Blocked reasons: {'; '.join(reasons)}. "
                    f"Pressed by {request.user.username}. "
                    f"Approved by Admin {admin_user.username}. "
                    f"Pushed PPPoE '{customer.pppoe_username}' to {router.device_name} "
                    f"with profile '{desired_profile(customer)}'."
                ),
            )
            messages.success(
                request,
                f"Override approved by {admin_user.username}. "
                f"{customer.full_name} pushed to {router.device_name}."
            )
        else:
            messages.error(request, f"Failed to push {customer.full_name}: {result.get('error')}")
    except Exception as e:
        messages.error(request, f"Error pushing {customer.full_name}: {str(e)}")

    return redirect("sync_manager")
