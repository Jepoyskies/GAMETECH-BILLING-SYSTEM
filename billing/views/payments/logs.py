from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
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
    SystemAdmin, SubscriptionPlan, Agent, AccountType,
    Customer, Barangay, Payment, Rebate, SystemLog, SmsLog, CignalPlay, AuditLog, AddOnRequest, Notification, ImprovementRequest, MessageTemplate
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar
from billing.views import calculate_new_expiration_date

@login_required
def payment_logs_view(request):
    payments = Payment.objects.all().order_by('-paid_at')

    # Filtering
    filter_from = request.GET.get('from', '')
    filter_to = request.GET.get('to', '')
    filter_search = request.GET.get('search', '')
    filter_method = request.GET.get('method', '')

    if filter_from:
        payments = payments.filter(paid_at__gte=filter_from + ' 00:00:00')
    if filter_to:
        payments = payments.filter(paid_at__lte=filter_to + ' 23:59:59')
    if filter_search:
        payments = payments.filter(
            Q(username__icontains=filter_search)
            | Q(reference_no__icontains=filter_search)
        )
    if filter_method:
        payments = payments.filter(payment_method=filter_method)

    # Summaries
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    grand_total = Payment.objects.aggregate(t=Sum('amount'))['t'] or 0
    filtered_range_total = payments.aggregate(t=Sum('amount'))['t'] or 0

    total_today = payments.filter(
        paid_at__date=today).aggregate(t=Sum('amount'))['t'] or 0
    total_yesterday = payments.filter(
        paid_at__date=yesterday).aggregate(t=Sum('amount'))['t'] or 0

    # 14 days chart data
    chart_labels = []
    chart_values = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        chart_labels.append(d.strftime('%Y-%m-%d'))
        daily_total = payments.filter(
            paid_at__date=d).aggregate(t=Sum('amount'))['t'] or 0
        chart_values.append(float(daily_total))

    # Pagination
    per_page = int(request.GET.get('per_page', 35))
    paginator = Paginator(payments, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    methods = Payment.objects.exclude(payment_method__isnull=True).exclude(
        payment_method='').values_list('payment_method', flat=True).distinct().order_by('payment_method')

    context = {
        'page_obj': page_obj,
        'filter_from': filter_from,
        'filter_to': filter_to,
        'filter_search': filter_search,
        'filter_method': filter_method,
        'methods': methods,
        'all_customers': Customer.objects.all().order_by('full_name'),

        'grand_total': grand_total,
        'filtered_range_total': filtered_range_total,
        'total_today': total_today,
        'total_yesterday': total_yesterday,

        'chart_labels_js': json.dumps(chart_labels),
        'chart_values_js': json.dumps(chart_values),
    }
    
    q = request.GET.copy()
    if 'page' in q:
        del q['page']
    context['query_params'] = q.urlencode()

    return render(request, 'billing/payment_logs.html', context)

@login_required
def rebates_logs_view(request):
    from billing.models import Rebate
    rebates = Rebate.objects.all().order_by('-paid_at')

    search = request.GET.get('search', '').strip()
    if search:
        rebates = rebates.filter(
            Q(username__icontains=search) |
            Q(plan_name__icontains=search) |
            Q(adjusted_by__icontains=search) |
            Q(note__icontains=search)
        )

    context = {
        'rebates': rebates,
        'search': search,
    }
    return render(request, 'billing/rebates_logs.html', context)

@login_required
def payment_addon_logs_view(request):
    """
    Replicates the legacy 'payment_addon_logs.php' view showing
    customers and their current plan status.
    """
    customers = Customer.objects.select_related('plan').all().order_by('-created_at')
    
    # Calculate simple stats
    now = timezone.now()
    active_count = customers.filter(expires_at__gte=now).count()
    expired_count = customers.filter(expires_at__lt=now).count()
    no_plan_count = customers.filter(plan__isnull=True).count()

    context = {
        'customers': customers,
        'active_count': active_count,
        'expired_count': expired_count,
        'no_plan_count': no_plan_count,
        'now': now,
    }
    return render(request, 'billing/payment_addon_logs.html', context)

