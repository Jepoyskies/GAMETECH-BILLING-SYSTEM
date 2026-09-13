from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
    permission_required,
)
from django.views.decorators.http import require_POST
from billing.decorators import role_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, Max
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime
from billing.models import (
    SystemAdmin,
    SubscriptionPlan,
    Agent,
    AccountType,
    Customer,
    Barangay,
    Payment,
    Rebate,
    SystemLog,
    SmsLog,
    CignalPlay,
    AuditLog,
    AddOnRequest,
    Notification,
    ImprovementRequest,
    MessageTemplate,
    AddonPlan,
)
from billing.forms import AddonPlanForm
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar


@login_required
def settings_view(request):
    return render(request, "billing/settings.html")


@role_required(["Admin"])
@login_required
def admin_panel_view(request):
    user_role = getattr(request.user, "role", "Viewer")
    if user_role != "Admin":
        messages.error(
            request, "Access denied. Only Admins can access the Admin Panel."
        )
        return redirect("dashboard")

    return render(request, "billing/admin_panel.html")

from .system_logs import system_logs_view


@login_required
def account_type_list(request):
    account_types = AccountType.objects.all().order_by("type_name")
    return render(
        request,
        "billing/settings_list.html",
        {
            "items": account_types,
            "title": "Manage Account Types",
            "item_name": "Account Type",
            "create_url": "create_account_type",
            "edit_url_name": "edit_account_type",
            "delete_url_name": "delete_account_type",
        },
    )


@login_required
def create_account_type(request):
    if request.method == "POST":
        form = AccountTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account Type created successfully!")
            return redirect("account_type_list")
    else:
        form = AccountTypeForm()
    return render(
        request,
        "billing/settings_form.html",
        {"form": form, "title": "Create Account Type", "back_url": "account_type_list"},
    )


@role_required(["Admin", "Editor"])
@login_required
def edit_account_type(request, pk):
    obj = get_object_or_404(AccountType, pk=pk)
    if request.method == "POST":
        form = AccountTypeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Account Type updated successfully!")
            return redirect("account_type_list")
    else:
        form = AccountTypeForm(instance=obj)
    return render(
        request,
        "billing/settings_form.html",
        {"form": form, "title": "Edit Account Type", "back_url": "account_type_list"},
    )


@role_required(["Admin", "Editor"])
@login_required
def delete_account_type(request, pk):
    obj = get_object_or_404(AccountType, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Account Type deleted successfully!")
    return redirect("account_type_list")


@login_required
def barangay_list(request):
    barangays = Barangay.objects.all().order_by("name")
    return render(
        request,
        "billing/settings_list.html",
        {
            "items": barangays,
            "title": "Manage Barangays",
            "item_name": "Barangay",
            "create_url": "create_barangay",
            "edit_url_name": "edit_barangay",
            "delete_url_name": "delete_barangay",
        },
    )


@login_required
def create_barangay(request):
    if request.method == "POST":
        form = BarangayForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Barangay created successfully!")
            return redirect("barangay_list")
    else:
        form = BarangayForm()
    return render(
        request,
        "billing/settings_form.html",
        {"form": form, "title": "Create Barangay", "back_url": "barangay_list"},
    )


@login_required
def edit_barangay(request, pk):
    obj = get_object_or_404(Barangay, pk=pk)
    if request.method == "POST":
        form = BarangayForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Barangay updated successfully!")
            return redirect("barangay_list")
    else:
        form = BarangayForm(instance=obj)
    return render(
        request,
        "billing/settings_form.html",
        {"form": form, "title": "Edit Barangay", "back_url": "barangay_list"},
    )


@login_required
def delete_barangay(request, pk):
    obj = get_object_or_404(Barangay, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Barangay deleted successfully!")
    return redirect("barangay_list")


@login_required
def backup_database_view(request):
    db_path = settings.DATABASES["default"]["NAME"]
    if os.path.exists(db_path):
        response = FileResponse(
            open(db_path, "rb"),
            as_attachment=True,
            filename=f"gametech_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.sqlite3",
        )
        return response

    messages.error(request, "Database file not found.")
    return redirect("settings")


@login_required
def submit_improvement_request(request):
    """AJAX endpoint to submit an improvement request from Sir Romnick."""
    if request.method == "POST":
        import json

        try:
            data = json.loads(request.body)
            msg = data.get("message", "").strip()
            if not msg:
                return JsonResponse(
                    {"success": False, "error": "Message cannot be empty."}
                )
            ImprovementRequest.objects.create(
                submitted_by=request.user,
                message=msg,
            )
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid method."})


@login_required
@role_required(["Admin"])
def improvement_requests_list(request):
    """Admin page to view all submitted improvement requests."""
    requests_qs = ImprovementRequest.objects.select_related("submitted_by").all()
    return render(
        request,
        "billing/improvement_requests.html",
        {"improvement_requests": requests_qs},
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def changelog_view(request):
    return render(request, "billing/changelog.html")


@login_required
@role_required(["Admin"])
def import_legacy_data_view(request):
    import csv
    import io
    from django.contrib import messages
    from django.core.management import call_command
    from django.http import HttpResponseRedirect
    from django.urls import reverse

    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        if not csv_file:
            messages.error(request, "Please upload a CSV file.")
            return HttpResponseRedirect(reverse("import_legacy_data"))

        if not csv_file.name.endswith(".csv"):
            messages.error(request, "File must be a CSV.")
            return HttpResponseRedirect(reverse("import_legacy_data"))

        try:
            # We save the file to a temp location so the management command can read it
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                for chunk in csv_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            # Run the migration command
            call_command("core_migration", tmp_path)
            messages.success(request, "Legacy data imported successfully!")
        except Exception as e:
            messages.error(request, f"Error during migration: {str(e)}")

        return HttpResponseRedirect(reverse("import_legacy_data"))

    return render(request, "billing/import_data.html")


@login_required
@role_required(["Admin"])
def message_templates_view(request):
    templates = MessageTemplate.objects.all().order_by("id")
    return render(request, "billing/message_templates.html", {"templates": templates})


@login_required
@role_required(["Admin"])
@require_POST
def update_message_template(request, template_id):
    template = get_object_or_404(MessageTemplate, id=template_id)
    template.body = request.POST.get("body", template.body)
    if template.type == "EMAIL":
        template.subject = request.POST.get("subject", template.subject)
    template.save()
    messages.success(request, f"Template '{template.name}' updated successfully.")
    return redirect("message_templates")


# ==========================================
# AddonPlan Pricing Management (Admin Only)
# ==========================================

@login_required
@role_required(["Admin"])
def addon_plan_list(request):
    user_role = getattr(request.user, "role", None)
    if user_role != "Admin" and not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Access denied. Only Admins can access Add-on Pricing.")
        return redirect("admin_panel")

    plans = AddonPlan.objects.all().order_by("price")
    form = AddonPlanForm()

    context = {
        "plans": plans,
        "form": form,
        "title": "Add-on Pricing Configuration",
        "total_count": plans.count(),
        "active_count": plans.filter(is_active=True).count(),
        "cignal_play_count": plans.filter(addon_type="Cignal Play").count(),
        "cignal_box_count": plans.filter(addon_type="Cignal Box").count(),
    }
    return render(request, "billing/addon_plans_list.html", context)


@login_required
@role_required(["Admin"])
def create_addon_plan(request):
    user_role = getattr(request.user, "role", None)
    if user_role != "Admin" and not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Access denied. Only Admins can create Add-on Plans.")
        return redirect("admin_panel")

    if request.method == "POST":
        form = AddonPlanForm(request.POST)
        try:
            if form.is_valid():
                plan = form.save()
                messages.success(request, f"Add-on Plan '{plan.name}' created successfully!")
            else:
                err_list = [f"{f}: {e[0]}" for f, e in form.errors.items()]
                messages.error(request, f"Could not create plan: {'; '.join(err_list)}")
        except Exception as e:
            messages.error(request, f"Error saving Add-on Plan: {str(e)}")
    return redirect("addon_plan_list")


@login_required
@role_required(["Admin"])
def edit_addon_plan(request, pk):
    user_role = getattr(request.user, "role", None)
    if user_role != "Admin" and not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Access denied. Only Admins can edit Add-on Plans.")
        return redirect("admin_panel")

    plan = get_object_or_404(AddonPlan, pk=pk)
    if request.method == "POST":
        form = AddonPlanForm(request.POST, instance=plan)
        try:
            if form.is_valid():
                updated = form.save()
                messages.success(request, f"Add-on Plan '{updated.name}' updated successfully!")
            else:
                err_list = [f"{f}: {e[0]}" for f, e in form.errors.items()]
                messages.error(request, f"Could not update plan: {'; '.join(err_list)}")
        except Exception as e:
            messages.error(request, f"Error updating Add-on Plan: {str(e)}")
    return redirect("addon_plan_list")


@login_required
@role_required(["Admin"])
def delete_addon_plan(request, pk):
    user_role = getattr(request.user, "role", None)
    if user_role != "Admin" and not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Access denied. Only Admins can delete Add-on Plans.")
        return redirect("admin_panel")

    plan = get_object_or_404(AddonPlan, pk=pk)
    if request.method == "POST":
        try:
            name = plan.name
            plan.delete()
            messages.success(request, f"Add-on Plan '{name}' deleted successfully!")
        except Exception as e:
            messages.error(request, f"Error deleting Add-on Plan: {str(e)}")
    return redirect("addon_plan_list")


@login_required
@role_required(["Admin"])
def toggle_addon_plan(request, pk):
    user_role = getattr(request.user, "role", None)
    if user_role != "Admin" and not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Access denied. Only Admins can modify Add-on Plans.")
        return redirect("admin_panel")

    plan = get_object_or_404(AddonPlan, pk=pk)
    if request.method == "POST":
        try:
            plan.is_active = not plan.is_active
            plan.save()
            status_label = "activated" if plan.is_active else "deactivated"
            messages.success(request, f"Add-on Plan '{plan.name}' {status_label} successfully!")
        except Exception as e:
            messages.error(request, f"Error toggling Add-on Plan status: {str(e)}")
    return redirect("addon_plan_list")

