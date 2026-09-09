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


@login_required
def notifications_list_view(request):
    notification_list = Notification.objects.all().order_by("-created_at")

    # Filter by type if provided
    notif_type = request.GET.get("type")
    if notif_type and notif_type != "all":
        notification_list = notification_list.filter(notification_type=notif_type)

    # Filter by read status if provided
    is_read = request.GET.get("status")
    if is_read == "unread":
        notification_list = notification_list.filter(is_read=False)
    elif is_read == "read":
        notification_list = notification_list.filter(is_read=True)

    paginator = Paginator(notification_list, 20)  # Show 20 notifications per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "billing/notifications.html",
        {
            "page_obj": page_obj,
            "current_type": notif_type or "all",
            "current_status": is_read or "all",
        },
    )


@login_required
def api_notifications(request):
    notifications = Notification.objects.all()[:15]
    unread_count = Notification.objects.filter(is_read=False).count()
    data = []
    for n in notifications:
        data.append(
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.notification_type,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
                "link": n.link or "#",
            }
        )
    return JsonResponse(
        {"status": "success", "unread_count": unread_count, "notifications": data}
    )


@login_required
@require_POST
def api_mark_notification_read(request, notif_id):
    try:
        notif = Notification.objects.get(id=notif_id)
        notif.is_read = True
        notif.save()
        return JsonResponse({"status": "success"})
    except Notification.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Not found"}, status=404)


@login_required
@require_POST
def api_mark_all_notifications_read(request):
    Notification.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({"status": "success"})
