from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
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
    Customer, Barangay, Payment, Rebate, SystemLog, SmsLog, CignalPlay, AuditLog, AddOnRequest, Notification, ImprovementRequest
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar
from billing.views.services import get_categorized_plans

@login_required
def customer_list(request):
    from network_manager.models import MikrotikDevice
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Case, When, Value, IntegerField
    
    customers = Customer.objects.select_related(
        'plan', 'agent', 'barangay', 'mikrotik_device').all()
        
    filter_type = request.GET.get('filter', 'all')
    
    now = timezone.now()
    seven_days_from_now = now + timedelta(days=7)
    seven_days_ago = now - timedelta(days=7)
    
    if filter_type == 'active':
        customers = customers.filter(expires_at__gt=seven_days_from_now, status='active')
    elif filter_type == 'expiring':
        customers = customers.filter(expires_at__gt=now, expires_at__lte=seven_days_from_now, status='active')
    elif filter_type == 'expired':
        customers = customers.filter(expires_at__lte=now, expires_at__gt=seven_days_ago)
    elif filter_type == 'inactive':
        customers = customers.filter(expires_at__lte=seven_days_ago)
        
    customers = customers.annotate(
        status_order=Case(
            When(status='active', then=Value(1)),
            When(status='pending', then=Value(2)),
            When(status='suspended', then=Value(3)),
            When(status='expired', then=Value(4)),
            When(status='inactive', then=Value(5)),
            When(status='pull out', then=Value(6)),
            default=Value(7),
            output_field=IntegerField(),
        )
    ).order_by('status_order', 'full_name')
        
    devices = MikrotikDevice.objects.all().order_by('device_name')
    from billing.models import Barangay
    barangays = Barangay.objects.all().order_by('name')
    return render(request, 'billing/customer_list.html', {
        'customers': customers,
        'devices': devices,
        'barangays': barangays,
        'filter_type': filter_type
    })

@login_required
def mac_history_view(request):
    from billing.models import CustomerMacHistory
    history = CustomerMacHistory.objects.select_related('customer').all()
    search = request.GET.get('search', '').strip()
    if search:
        history = history.filter(
            Q(customer__full_name__icontains=search) |
            Q(mac_address__icontains=search) |
            Q(customer__id__icontains=search)
        )
    return render(request, 'billing/mac_history.html', {'history': history})

