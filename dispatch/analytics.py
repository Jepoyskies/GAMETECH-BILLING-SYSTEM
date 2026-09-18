import json
from datetime import datetime
from django.utils import timezone
from django.db.models import Q
from .models import JobTicket


def get_operational_overview_stats():
    """
    Section 1: Operational Overview (4 Colored Cards - ALWAYS LIVE)
    For Dispatch, Ongoing, Total Closed, Total Cancelled.
    Each with an Install / Repair breakdown underneath.
    Bypasses date filters per Phase 1 rule.
    """
    pending = JobTicket.objects.filter(status='PENDING')
    ongoing = JobTicket.objects.filter(status__in=['ASSIGNED', 'IN_PROGRESS'])
    closed = JobTicket.objects.filter(status__in=['COMPLETED', 'QA_PASSED'])
    cancelled = JobTicket.objects.filter(status='CANCELLED')

    return {
        'for_dispatch': {
            'total': pending.count(),
            'installs': pending.exclude(ticket_type='REPAIR').count(),
            'repairs': pending.filter(ticket_type='REPAIR').count(),
        },
        'ongoing': {
            'total': ongoing.count(),
            'installs': ongoing.exclude(ticket_type='REPAIR').count(),
            'repairs': ongoing.filter(ticket_type='REPAIR').count(),
        },
        'closed': {
            'total': closed.count(),
            'installs': closed.exclude(ticket_type='REPAIR').count(),
            'repairs': closed.filter(ticket_type='REPAIR').count(),
        },
        'cancelled': {
            'total': cancelled.count(),
            'installs': cancelled.exclude(ticket_type='REPAIR').count(),
            'repairs': cancelled.filter(ticket_type='REPAIR').count(),
        }
    }


def get_overview_kpis_and_chart(date_filter='all', date_from=None, date_to=None):
    """
    Section 2: Overview Section (Filtered by Created At / selected date filter)
    Stacked KPI cards on left: Total Dispatches, Installations, Repairs, Concerns.
    Donut / Status distribution chart on right with category cycle tabs:
    All Records -> Internet Install -> Cignal Play -> Client Concerns.
    """
    today = timezone.now().date()
    qs = JobTicket.objects.all()

    if date_filter == 'today':
        qs = qs.filter(created_at__date=today)
    elif date_filter == 'this_month':
        qs = qs.filter(created_at__year=today.year, created_at__month=today.month)
    elif date_filter == 'custom' and date_from and date_to:
        qs = qs.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)

    total_dispatches = qs.count()
    installations = qs.filter(ticket_type='INSTALLATION').count()
    repairs = qs.filter(ticket_type='REPAIR').count()
    concerns = qs.filter(Q(source_tab='CLIENT_CONCERNS') | Q(chat_type__icontains='concern')).count()

    def get_status_counts(sub_qs):
        return {
            'pending': sub_qs.filter(status='PENDING').count(),
            'assigned': sub_qs.filter(status='ASSIGNED').count(),
            'in_progress': sub_qs.filter(status='IN_PROGRESS').count(),
            'completed': sub_qs.filter(status__in=['COMPLETED', 'QA_PASSED']).count(),
            'cancelled': sub_qs.filter(status='CANCELLED').count(),
        }

    chart_data = {
        'all': get_status_counts(qs),
        'internet_install': get_status_counts(qs.filter(source_tab='INTERNET_INSTALL')),
        'cignal_play': get_status_counts(qs.filter(source_tab='CIGNAL_PLAY')),
        'client_concerns': get_status_counts(qs.filter(Q(source_tab='CLIENT_CONCERNS') | Q(chat_type__icontains='concern'))),
    }

    return {
        'total_dispatches': total_dispatches,
        'installations': installations,
        'repairs': repairs,
        'concerns': concerns,
        'chart_data_json': json.dumps(chart_data),
    }


def get_monitoring_summary(date_filter='all', date_from=None, date_to=None):
    """
    Section 3: Monitoring Summary (3 Cards: Internet Install, Cignal Play, Client Concerns)
    Each showing Total / Completed / Cancelled, filtered by Completed At (or done_at).
    """
    today = timezone.now().date()
    qs = JobTicket.objects.all()

    if date_filter == 'today':
        completed_filter = Q(done_at__date=today)
        cancelled_filter = Q(updated_at__date=today, status='CANCELLED')
        total_filter = Q(created_at__date=today) | completed_filter
    elif date_filter == 'this_month':
        completed_filter = Q(done_at__year=today.year, done_at__month=today.month)
        cancelled_filter = Q(updated_at__year=today.year, updated_at__month=today.month, status='CANCELLED')
        total_filter = Q(created_at__year=today.year, created_at__month=today.month) | completed_filter
    elif date_filter == 'custom' and date_from and date_to:
        completed_filter = Q(done_at__date__gte=date_from, done_at__date__lte=date_to)
        cancelled_filter = Q(updated_at__date__gte=date_from, updated_at__date__lte=date_to, status='CANCELLED')
        total_filter = Q(created_at__date__gte=date_from, created_at__date__lte=date_to) | completed_filter
    else:
        completed_filter = Q(status__in=['COMPLETED', 'QA_PASSED'])
        cancelled_filter = Q(status='CANCELLED')
        total_filter = Q()

    def get_summary_card(source_tab_val, extra_q=None):
        base = qs.filter(source_tab=source_tab_val) if not extra_q else qs.filter(extra_q)
        total = base.filter(total_filter).count() if total_filter else base.count()
        completed = base.filter(status__in=['COMPLETED', 'QA_PASSED']).filter(completed_filter).count()
        cancelled = base.filter(status='CANCELLED').filter(cancelled_filter).count()
        return {'total': total, 'completed': completed, 'cancelled': cancelled}

    return {
        'internet_install': get_summary_card('INTERNET_INSTALL'),
        'cignal_play': get_summary_card('CIGNAL_PLAY'),
        'client_concerns': get_summary_card('CLIENT_CONCERNS', Q(source_tab='CLIENT_CONCERNS') | Q(chat_type__icontains='concern')),
    }


def get_monthly_targets_data():
    """
    Section 4: Monthly Install Targets bar chart data:
    Gray bar = target (default 100), Blue bar = actual completed installs.
    Mini-cards per month showing % reached (green at 100%).
    Dashed average-target reference line.
    """
    now = timezone.now()
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_stats = []
    default_monthly_target = 100

    current_month_idx = now.month
    start_month = max(1, current_month_idx - 5)
    
    total_targets = 0
    months_count = 0

    for m in range(start_month, current_month_idx + 1):
        target = default_monthly_target
        actual = JobTicket.objects.filter(
            ticket_type='INSTALLATION',
            status__in=['COMPLETED', 'QA_PASSED'],
            done_at__year=now.year,
            done_at__month=m
        ).count()

        pct = round((actual / target) * 100.0, 1) if target > 0 else 0.0
        is_reached = (pct >= 100.0)

        monthly_stats.append({
            'month_name': month_names[m - 1],
            'month_num': m,
            'target': target,
            'actual': actual,
            'pct': pct,
            'is_reached': is_reached,
        })
        total_targets += target
        months_count += 1

    avg_target = round(total_targets / months_count, 0) if months_count > 0 else default_monthly_target

    return {
        'months': monthly_stats,
        'avg_target': avg_target,
        'months_json': json.dumps(monthly_stats),
    }
