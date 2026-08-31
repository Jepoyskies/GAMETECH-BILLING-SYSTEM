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

@login_required
def dashboard_view(request):
    if hasattr(request.user, 'role') and request.user.role == 'Agent':
        return redirect('customer_list')
        
    today = timezone.localtime().date()
    now = timezone.localtime()

    # KPIs
    total_customers = Customer.objects.count()
    new_customers_this_month = Customer.objects.filter(
        created_at__month=today.month, created_at__year=today.year).count()

    # Totals
    yesterday = today - timedelta(days=1)
    start_of_week = today - timedelta(days=today.weekday())
    
    payments = Payment.objects.all()
    
    total_today = payments.filter(created_at__date=today).aggregate(t=Sum('amount'))['t'] or 0
    total_yesterday = payments.filter(created_at__date=yesterday).aggregate(t=Sum('amount'))['t'] or 0
    total_week = payments.filter(created_at__date__gte=start_of_week).aggregate(t=Sum('amount'))['t'] or 0
    total_month = payments.filter(created_at__month=today.month, created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0
    total_year = payments.filter(created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0

    totals = {
        'today': f"{total_today:,.2f}",
        'yesterday': f"{total_yesterday:,.2f}",
        'week': f"{total_week:,.2f}",
        'month': f"{total_month:,.2f}",
        'year': f"{total_year:,.2f}",
    }

    # Revenue Growth
    last_month_dt = today.replace(day=1) - timedelta(days=1)
    total_last_month = payments.filter(created_at__month=last_month_dt.month, created_at__year=last_month_dt.year).aggregate(t=Sum('amount'))['t'] or 0
    
    if total_last_month > 0:
        growth_percent = ((float(total_month) - float(total_last_month)) / float(total_last_month)) * 100
    else:
        growth_percent = 100.0 if total_month > 0 else 0.0

    growth_icon = 'fa-arrow-up' if growth_percent >= 0 else 'fa-arrow-down'
    growth_color = 'text-success' if growth_percent >= 0 else 'text-danger'

    # Collection Rate
    distinct_payers_this_month = payments.filter(created_at__month=today.month, created_at__year=today.year).values('customer').distinct().count()
    collection_rate = (distinct_payers_this_month / total_customers * 100) if total_customers > 0 else 0

    # Sales by Month Chart
    months_js = []
    sales_by_month_js = []
    for i in range(11, -1, -1):
        m = (today.month - 1 - i) % 12 + 1
        y = today.year + ((today.month - 1 - i) // 12)
        month_name = calendar.month_abbr[m]
        months_js.append(month_name)
        m_total = payments.filter(created_at__month=m, created_at__year=y).aggregate(t=Sum('amount'))['t'] or 0
        sales_by_month_js.append(float(m_total))

    # Sales by Day (Last 7 days)
    days_js = []
    sales_by_day_js = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        days_js.append(d.strftime("%a"))
        d_total = payments.filter(created_at__date=d).aggregate(t=Sum('amount'))['t'] or 0
        sales_by_day_js.append(float(d_total))

    # Pie Chart
    cash = payments.filter(payment_method='Cash', created_at__month=today.month, created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0
    gcash = payments.filter(payment_method='GCash', created_at__month=today.month, created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0
    bank = payments.filter(payment_method='Bank Transfer', created_at__month=today.month, created_at__year=today.year).aggregate(t=Sum('amount'))['t'] or 0
    
    pie_labels_js = ["Cash", "GCash", "Bank Transfer"]
    pie_data_js = [float(cash), float(gcash), float(bank)]

    # Admin logins (fetch last active from cache and historical from SystemLog)
    recent_users = User.objects.filter(is_active=True).exclude(last_login__isnull=True)
    recent_admin_logins = []
    
    from django.core.cache import cache
    from billing.models import SystemLog
    
    active_usernames = set()
    
    # 1. Get currently active users
    for u in recent_users:
        last_active = cache.get(f'seen_user_{u.id}')
        if last_active:
            recent_admin_logins.append({
                'username': u.username,
                'color': '#0d6efd',
                'event_type': 'active',
                'login_time': last_active
            })
            active_usernames.add(u.username)
            
    # 2. Get recent historical logins
    recent_logs = SystemLog.objects.filter(table_name='User', action='LOGIN').order_by('-changed_at')[:10]
    for log in recent_logs:
        # Don't show a "login" event for someone if they are currently marked "active" right now
        # Also limit duplicates if they logged in multiple times today
        if log.changed_by not in active_usernames:
            recent_admin_logins.append({
                'username': log.changed_by,
                'color': '#0d6efd',
                'event_type': 'login',
                'login_time': log.changed_at
            })
            active_usernames.add(log.changed_by)
            
    # 3. Fallback for users who haven't logged in recently enough to be in SystemLog
    for u in recent_users:
        if u.username not in active_usernames and u.last_login:
            recent_admin_logins.append({
                'username': u.username,
                'color': '#0d6efd',
                'event_type': 'login',
                'login_time': u.last_login
            })
            active_usernames.add(u.username)
            
    # Sort by display_time descending and take top 5
    recent_admin_logins = sorted(recent_admin_logins, key=lambda x: x['login_time'], reverse=True)[:5]

    # Top Paying Clients
    top_clients_qs = payments.values('customer__full_name', 'customer__pppoe_username').annotate(
        total_paid=Sum('amount'), last_payment=Max('created_at')
    ).order_by('-total_paid')[:5]

    top_clients = []
    for c in top_clients_qs:
        if c['customer__full_name'] or c['customer__pppoe_username']:
            top_clients.append({
                'username': c['customer__pppoe_username'] or c['customer__full_name'],
                'total_paid': c['total_paid'],
                'last_payment': c['last_payment']
            })

    # Top Service Plans
    top_plans_qs = Customer.objects.values('plan__name').annotate(
        cnt=Count('id')).order_by('-cnt')[:5]
    top_plans = [{'plan_name': p['plan__name'] or 'None',
                  'cnt': p['cnt']} for p in top_plans_qs]

    # Expiring Users (Next 3 days & recently expired)
    three_days_ahead = now + timedelta(days=3)
    expiring_qs = Customer.objects.filter(expires_at__isnull=False, expires_at__lte=three_days_ahead).order_by('-expires_at')[:5]
    expiring_users = []
    for u in expiring_qs:
        is_expired = u.expires_at < now
        expiring_users.append({
            'username': u.pppoe_username or u.full_name,
            'plan_name': u.plan.name if u.plan else 'N/A',
            'expires_at': u.expires_at,
            'is_expired': is_expired,
            'expires_at_epoch': int(u.expires_at.timestamp())
        })

    context = {
        'growth_percent': growth_percent,
        'growth_icon': growth_icon,
        'growth_color': growth_color,
        'growth_percent_formatted': f"{growth_percent:.1f}",
        'new_customers_this_month': new_customers_this_month,
        'collection_rate_formatted': f"{collection_rate:.1f}",
        'distinct_payers_this_month': distinct_payers_this_month,
        'total_customers': total_customers,
        'totals': totals,
        'recent_admin_logins': recent_admin_logins,
        'top_clients': top_clients,
        'top_plans': top_plans,
        'expiring_users': expiring_users,
        'months_js': json.dumps(months_js),
        'sales_by_month_js': json.dumps(sales_by_month_js),
        'days_js': json.dumps(days_js),
        'sales_by_day_js': json.dumps(sales_by_day_js),
        'pie_labels_js': json.dumps(pie_labels_js),
        'pie_data_js': json.dumps(pie_data_js),
    }

    return render(request, 'billing/dashboard.html', context)


