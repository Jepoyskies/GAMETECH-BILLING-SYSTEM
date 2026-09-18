from django.shortcuts import render, redirect
from django.utils import timezone
from django.core.paginator import Paginator
import datetime
from billing.models import Customer, Payment, SubscriptionPlan, MonitoredService
import re

import logging
logger = logging.getLogger(__name__)

STATUS_PRIORITY = {
    'Excellent': 0, 'Active': 0, 'Good': 0,
    'Moderate': 1, 'Maintenance': 1,
    'Poor': 2, 'Disconnected': 2,
    'Offline': 3, 'Outage': 4,
}

def _get_priority(status):
    return STATUS_PRIORITY.get(status, 0)


def portal_dashboard(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('customer_portal:portal_login')
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect('customer_portal:portal_login')

    if customer.must_change_password:
        return redirect('customer_portal:force_change_password')

    plan = customer.plan
    payments = Payment.objects.filter(customer=customer).order_by('-created_at')[:10]
    plans = SubscriptionPlan.objects.all().order_by('price')

    effective_status = 'Excellent'
    effective_reason = 'Your service is running normally.'
    is_network_issue = False

    if customer.health_status and _get_priority(customer.health_status) > _get_priority(effective_status):
        effective_status = customer.health_status
        effective_reason = customer.health_reason or "We have detected an issue with your connection."
        is_network_issue = True

    if customer.barangay and _get_priority(customer.barangay.health_status) > _get_priority(effective_status):
        effective_status = customer.barangay.health_status
        effective_reason = customer.barangay.health_reason or f"Network issue reported in {customer.barangay.name}"
        is_network_issue = True

    if customer.mikrotik_device and _get_priority(customer.mikrotik_device.health_status) > _get_priority(effective_status):
        effective_status = customer.mikrotik_device.health_status
        effective_reason = customer.mikrotik_device.health_reason or "Network issue reported for your sector"
        is_network_issue = True

    is_account_suspended = customer.status in ['suspended', 'expired', 'inactive']
    if is_account_suspended:
        effective_status = 'Disconnected'
        effective_reason = "Your account has been suspended due to an overdue balance. Please pay your bill to restore connection."
        is_network_issue = True

    is_expiring_soon = False
    days_until_expiry = None
    if customer.expires_at:
        delta = customer.expires_at - timezone.now()
        days_until_expiry = delta.days
        if customer.status == 'active' and 0 < days_until_expiry <= 3:
            is_expiring_soon = True

    issue_services = MonitoredService.objects.exclude(status='Up').order_by('-latency_ms')[:10]
    cignal_plans = customer.cignal_plans.all().order_by('-created_at')
    customer_tickets = customer.job_tickets.all().order_by('-created_at')
    open_tickets_count = customer_tickets.filter(status__in=['PENDING', 'ASSIGNED', 'IN_PROGRESS']).count()
    recent_ticket = customer_tickets.first()

    speed_down_val = 0.0
    speed_up_val = 0.0
    if plan:
        sd_match = re.search(r'([\d.]+)', plan.speed_down or "")
        su_match = re.search(r'([\d.]+)', plan.speed_up or "")
        if sd_match: speed_down_val = float(sd_match.group(1))
        if su_match: speed_up_val = float(su_match.group(1))

    context = {
        'customer': customer,
        'plan': plan,
        'effective_status': effective_status,
        'effective_reason': effective_reason,
        'is_network_issue': is_network_issue,
        'is_account_suspended': is_account_suspended,
        'is_expiring_soon': is_expiring_soon,
        'days_until_expiry': days_until_expiry,
        'payments': payments,
        'plans': plans,
        'cignal_plans': cignal_plans,
        'issue_services': issue_services,
        'open_tickets_count': open_tickets_count,
        'recent_ticket': recent_ticket,
        'total_tickets_count': customer_tickets.count(),
        'speed_down_val': speed_down_val,
        'speed_up_val': speed_up_val,
    }
    return render(request, 'customer_portal/portal_dashboard.html', context)


def portal_statement_view(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('customer_portal:portal_login')
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect('customer_portal:portal_login')
    if customer.must_change_password:
        return redirect('customer_portal:force_change_password')

    payments_qs = Payment.objects.filter(customer=customer).order_by('-created_at')
    
    available_years = list(payments_qs.dates('created_at', 'year', order='DESC'))
    available_years = [d.year for d in available_years]
    
    year_str = request.GET.get('year')
    if year_str and year_str.isdigit():
        current_year = int(year_str)
    else:
        current_year = datetime.date.today().year

    payments_qs = payments_qs.filter(created_at__year=current_year)
    total_paid = sum(p.amount for p in payments_qs)

    return render(request, 'customer_portal/portal_statement.html', {
        'customer': customer,
        'payments': payments_qs,
        'available_years': available_years,
        'current_year': current_year,
        'total_paid': total_paid,
    })
