from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.views.decorators.http import require_POST
from ..decorators import role_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, Max
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime
from ..models import (
    SystemAdmin, SubscriptionPlan, Agent, AccountType,
    Customer, Barangay, Payment, Rebate, SystemLog, SmsLog, CignalPlay, AuditLog, AddOnRequest, Notification, ImprovementRequest
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar

def add_one_month(dt: datetime) -> datetime:
    """Adds exactly one calendar month to a datetime object."""
    month = dt.month
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def calculate_new_expiration_date(current_expiration_date: datetime, payment_amount: float, plan_monthly_price: float) -> datetime:
    if plan_monthly_price <= 0 or payment_amount <= 0:
        return current_expiration_date

    # 1. Full Month Exception
    if payment_amount == plan_monthly_price:
        return add_one_month(current_expiration_date)

    # 2. Price Per Day Calculation
    price_per_day = plan_monthly_price / 30.0

    # 3. Prorated Days Granted
    days_granted = payment_amount / price_per_day
    return current_expiration_date + timedelta(days=days_granted)


@login_required
@role_required(['Admin', 'Editor', 'CSR'])
def send_semaphore_sms(phone, message):
    api_key = 'a1be64e85146a946d40aeb1677d37a48'
    url = 'https://api.semaphore.co/api/v4/messages'
    payload = {
        'apikey': api_key,
        'number': phone,
        'message': message,
        'sendername': 'SEMAPHORE'
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        return response.text, response.status_code == 200
    except Exception as e:
        return str(e), False


from .settings import *
from .customers import *
from .payments import *
from .services import *
from .dashboard import *
from .network import *
from .auth import *
from .api import *
