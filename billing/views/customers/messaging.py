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
@require_POST
def bulk_sms_view(request):
    import json
    import time

    try:
        data = json.loads(request.body)
        customer_ids = data.get("customer_ids", [])
        message = data.get("message", "").strip()

        if not customer_ids or not message:
            return JsonResponse(
                {"success": False, "error": "Missing customers or message."}
            )

        customers = Customer.objects.filter(id__in=customer_ids)
        sent_count = 0

        for customer in customers:
            if customer.phone:
                response, is_success = send_semaphore_sms(customer.phone, message)
                if is_success:
                    sent_count += 1
                time.sleep(0.1)  # Prevent rate limiting

        return JsonResponse({"success": True, "sent_count": sent_count})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def bulk_email_view(request):
    import json
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        data = json.loads(request.body)
        customer_ids = data.get("customer_ids", [])
        subject = data.get("subject", "Important Notice").strip()
        message = data.get("message", "").strip()

        if not customer_ids or not message:
            return JsonResponse(
                {"success": False, "error": "Missing customers or message."}
            )

        customers = Customer.objects.filter(id__in=customer_ids)
        sent_count = 0
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@gametech.com")

        for customer in customers:
            if customer.email:
                try:
                    send_mail(
                        subject,
                        message,
                        from_email,
                        [customer.email],
                        fail_silently=False,
                    )
                    sent_count += 1
                except Exception as e:
                    print(f"Failed to send email to {customer.email}: {e}")

        return JsonResponse({"success": True, "sent_count": sent_count})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def sms_view(request):
    if request.method == "POST":
        if "send_sms_custom" in request.POST:
            phone = request.POST.get("phone")
            message = request.POST.get("message")

            response_text, is_success = send_semaphore_sms(phone, message)
            status = "success" if is_success else "error"

            SmsLog.objects.create(
                phone=phone, message=message, response=response_text, status=status
            )
            messages.info(request, f"SMS sent to {phone}. Response: {response_text}")

        elif "bulk_send_sms" in request.POST:
            phones_str = request.POST.get("selected_phones", "")
            bulk_message = request.POST.get("bulk_message")
            phones = [p.strip() for p in phones_str.split(",") if p.strip()]

            for phone in phones:
                response_text, is_success = send_semaphore_sms(phone, bulk_message)
                status = "success" if is_success else "error"
                SmsLog.objects.create(
                    phone=phone,
                    message=bulk_message,
                    response=response_text,
                    status=status,
                )
            messages.info(request, f"Bulk SMS sent to {len(phones)} recipients.")

        return redirect("sms_messaging")

    search = request.GET.get("search", "")
    customers = Customer.objects.exclude(pppoe_username__isnull=True).exclude(
        pppoe_username=""
    )

    if search:
        customers = customers.filter(
            Q(pppoe_username__icontains=search)
            | Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(address__icontains=search)
            | Q(status__icontains=search)
        )

    customers = customers.order_by("full_name")
    paginator = Paginator(customers, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    sms_logs = SmsLog.objects.all()[:100]

    context = {"page_obj": page_obj, "search": search, "sms_logs": sms_logs}

    q = request.GET.copy()
    if "page" in q:
        del q["page"]
    context["query_params"] = q.urlencode()
    return render(request, "billing/sms_messaging.html", context)
