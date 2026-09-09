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

@login_required
def live_addon_requests_api(request):
    requests = AddOnRequest.objects.filter(status='Pending').select_related('customer').order_by('-requested_at')
    data = []
    for req in requests:
        data.append({
            'id': req.id,
            'customer_name': req.customer.full_name,
            'customer_id': req.customer.id,
            'addon_type': req.addon_type,
            'requested_at': req.requested_at.strftime('%b %d, %I:%M %p')
        })
    return JsonResponse({'status': 'success', 'data': data})

@login_required
@require_POST
def resolve_addon_request_api(request):
    import json
    try:
        body = json.loads(request.body)
        req_id = body.get('request_id')
        if req_id:
            addon_req = AddOnRequest.objects.get(id=req_id)
            addon_req.status = 'Resolved'
            addon_req.save()
            return JsonResponse({'status': 'success'})
    except AddOnRequest.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

