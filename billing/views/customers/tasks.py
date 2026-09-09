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
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar
from billing.views.services import get_categorized_plans


@login_required
def auto_suspend_view(request):
    if request.method == "POST":
        usernames = request.POST.getlist("usernames")
        if not usernames:
            messages.error(request, "No users selected for suspension.")
            return redirect("auto_suspend")

        suspended_count = 0
        errors = []

        # Group by device to minimize connections
        customers_to_suspend = Customer.objects.filter(
            pppoe_username__in=usernames
        ).select_related("mikrotik_device")
        device_users = {}
        for c in customers_to_suspend:
            if c.mikrotik_device:
                if c.mikrotik_device not in device_users:
                    device_users[c.mikrotik_device] = []
                device_users[c.mikrotik_device].append(c)

        for device, users in device_users.items():
            api = MikrotikAPI(device)
            for user in users:
                success, msg = api.suspend_pppoe_user(user.pppoe_username)
                if success:
                    suspended_count += 1
                else:
                    errors.append(f"Failed to suspend {user.pppoe_username}: {msg}")

        if suspended_count > 0:
            messages.success(
                request, f"Successfully suspended {suspended_count} users."
            )
        if errors:
            for err in errors:
                messages.error(request, err)

        return redirect("auto_suspend")

    # GET request: fetch past due customers
    past_due_customers = (
        Customer.objects.filter(
            expires_at__lte=timezone.now(), mikrotik_device__isnull=False
        )
        .exclude(pppoe_username__isnull=True)
        .exclude(pppoe_username="")
        .select_related("mikrotik_device")
    )

    display_customers = []

    # Group by device for efficient querying
    device_customers = {}
    for c in past_due_customers:
        if c.mikrotik_device not in device_customers:
            device_customers[c.mikrotik_device] = []
        device_customers[c.mikrotik_device].append(c)

    for device, customers in device_customers.items():
        api = MikrotikAPI(device)
        secrets = api.get_ppp_secrets()

        # Build lookup dict
        secret_dict = {s.get("name"): s.get("profile", "N/A") for s in secrets}

        for c in customers:
            profile = secret_dict.get(c.username, "Not Found")
            if str(profile).lower() != "expired":
                c.mikrotik_profile = profile
                display_customers.append(c)

    display_customers.sort(key=lambda x: x.full_name)

    context = {"due_customers": display_customers}
    return render(request, "billing/auto_suspend.html", context)
