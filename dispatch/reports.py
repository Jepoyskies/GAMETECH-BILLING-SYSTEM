import math
from datetime import datetime
from django.utils import timezone
from django.db.models import Q, Count
from django.contrib.auth.models import User
from .models import JobTicket, Technician, Team


def calculate_close_rate(closed_count, handled_count, cancelled_count):
    """
    Proven Legacy v5.7.0 Close-Rate Formula:
    Excludes customer-initiated cancellations from the denominator:
    Close Rate = Closed / (Handled - Cancelled) * 100
    """
    effective_base = handled_count - cancelled_count
    if effective_base <= 0:
        return 0.0
    rate = (closed_count / effective_base) * 100.0
    return round(rate, 1)


def get_tier_info(rate):
    """
    Legacy Performance Color Tiers:
    >= 70% : Green (Success / High Performer)
    40% - 69.9% : Yellow (Warning / Average)
    < 40% : Red (Danger / Needs Attention)
    """
    if rate >= 70.0:
        return {
            'rate': rate,
            'tier': 'green',
            'badge_class': 'badge bg-success',
            'text_class': 'text-success',
            'color': '#10b981',
            'label': 'Optimal'
        }
    elif rate >= 40.0:
        return {
            'rate': rate,
            'tier': 'yellow',
            'badge_class': 'badge bg-warning text-dark',
            'text_class': 'text-warning',
            'color': '#f59e0b',
            'label': 'Average'
        }
    else:
        return {
            'rate': rate,
            'tier': 'red',
            'badge_class': 'badge bg-danger',
            'text_class': 'text-danger',
            'color': '#ef4444',
            'label': 'Needs Focus'
        }


def get_date_filtered_tickets(date_filter='all', date_from=None, date_to=None):
    """
    Helper to get base queryset filtered by operational date range.
    """
    today = timezone.now().date()
    qs = JobTicket.objects.all()

    if date_filter == 'today':
        qs = qs.filter(created_at__date=today)
    elif date_filter == 'this_month':
        qs = qs.filter(created_at__year=today.year, created_at__month=today.month)
    elif date_filter == 'custom' and date_from and date_to:
        qs = qs.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    return qs


def get_csr_performance_report(date_filter='all', date_from=None, date_to=None):
    """
    CSR Performance Table with 'Concerns Take Priority' rule:
    If ticket has chat_type == 'Concern' or source_tab == 'CLIENT_CONCERNS',
    it is strictly counted under Concerns Handled / Closed / Cancelled.
    Otherwise it is counted under Dispatches.
    Denominator excludes cancellations.
    """
    tickets = get_date_filtered_tickets(date_filter, date_from, date_to).select_related('created_by')
    
    # Collect all users who created or handled tickets
    user_ids = set()
    for t in tickets:
        if t.created_by_id:
            user_ids.add(t.created_by_id)
            
    # Include all active staff users so zero-ticket CSRs are also visible
    staff_users = User.objects.filter(Q(is_staff=True) | Q(id__in=user_ids)).order_by('first_name', 'username')
    
    csr_data = {}
    for user in staff_users:
        csr_data[user.id] = {
            'user': user,
            'name': user.get_full_name() or user.username,
            'disp_handled': 0,
            'disp_closed': 0,
            'disp_cancelled': 0,
            'concern_handled': 0,
            'concern_closed': 0,
            'concern_cancelled': 0,
            'total_handled': 0,
            'total_closed': 0,
            'total_cancelled': 0,
        }

    for t in tickets:
        u_id = t.created_by_id
        if not u_id or u_id not in csr_data:
            continue

        entry = csr_data[u_id]
        is_closed = t.status in ['COMPLETED', 'QA_PASSED']
        is_cancelled = t.status == 'CANCELLED'

        # RULE: 'Concerns take priority'
        # If chat_type == 'Concern' or source_tab == 'CLIENT_CONCERNS', bucket as concern
        is_concern = (t.source_tab == 'CLIENT_CONCERNS' or (t.chat_type and 'concern' in t.chat_type.lower()))

        entry['total_handled'] += 1
        if is_closed:
            entry['total_closed'] += 1
        if is_cancelled:
            entry['total_cancelled'] += 1

        if is_concern:
            entry['concern_handled'] += 1
            if is_closed:
                entry['concern_closed'] += 1
            if is_cancelled:
                entry['concern_cancelled'] += 1
        else:
            entry['disp_handled'] += 1
            if is_closed:
                entry['disp_closed'] += 1
            if is_cancelled:
                entry['disp_cancelled'] += 1

    # Calculate close rates and color tiers
    report_rows = []
    totals = {
        'disp_handled': 0, 'disp_closed': 0, 'disp_cancelled': 0,
        'concern_handled': 0, 'concern_closed': 0, 'concern_cancelled': 0,
        'total_handled': 0, 'total_closed': 0, 'total_cancelled': 0,
    }

    for row in csr_data.values():
        disp_rate = calculate_close_rate(row['disp_closed'], row['disp_handled'], row['disp_cancelled'])
        concern_rate = calculate_close_rate(row['concern_closed'], row['concern_handled'], row['concern_cancelled'])
        total_rate = calculate_close_rate(row['total_closed'], row['total_handled'], row['total_cancelled'])

        row['disp_rate'] = disp_rate
        row['disp_tier'] = get_tier_info(disp_rate)
        row['concern_rate'] = concern_rate
        row['concern_tier'] = get_tier_info(concern_rate)
        row['total_rate'] = total_rate
        row['total_tier'] = get_tier_info(total_rate)

        # Accumulate totals
        for key in totals:
            totals[key] += row[key]

        report_rows.append(row)

    # Sort rows by total closed descending, then total handled
    report_rows.sort(key=lambda r: (r['total_closed'], r['total_rate']), reverse=True)

    # Calculate overall totals close rates
    totals['disp_rate'] = calculate_close_rate(totals['disp_closed'], totals['disp_handled'], totals['disp_cancelled'])
    totals['disp_tier'] = get_tier_info(totals['disp_rate'])
    totals['concern_rate'] = calculate_close_rate(totals['concern_closed'], totals['concern_handled'], totals['concern_cancelled'])
    totals['concern_tier'] = get_tier_info(totals['concern_rate'])
    totals['total_rate'] = calculate_close_rate(totals['total_closed'], totals['total_handled'], totals['total_cancelled'])
    totals['total_tier'] = get_tier_info(totals['total_rate'])

    return {
        'rows': report_rows,
        'totals': totals
    }


def get_technician_productivity_report(date_filter='all', date_from=None, date_to=None):
    """
    Technicals Productivity Ranking (By Staff & By Team):
    - Target/Day (default 5)
    - Target/Month (default 100)
    - Installs (New Installation, Cignal, Migration, Relocation)
    - Repairs (Repair / Concern)
    - Total (Installs + Repairs)
    - % of Product: (Total / (Target/Month * months_count)) * 100
    - Per Day (avg): Total / (months_count * 26 working days)
    """
    # Working days & months calculation
    months_count = 1.0
    working_days = 26.0

    if date_filter == 'today':
        working_days = 1.0
        months_count = 1.0 / 26.0
    elif date_filter == 'custom' and date_from and date_to:
        try:
            d1 = datetime.strptime(str(date_from), "%Y-%m-%d").date()
            d2 = datetime.strptime(str(date_to), "%Y-%m-%d").date()
            days_span = max(1, (d2 - d1).days + 1)
            # Count non-sundays in the date range
            sundays = sum(1 for d in (d1 + timezone.timedelta(days=i) for i in range(days_span)) if d.weekday() == 6)
            working_days = float(max(1, days_span - sundays))
            months_count = max(1.0, round(working_days / 26.0, 2))
        except Exception:
            working_days = 26.0
            months_count = 1.0

    # Completed tickets queryset
    tickets_qs = get_date_filtered_tickets(date_filter, date_from, date_to).filter(
        status__in=['COMPLETED', 'QA_PASSED']
    ).prefetch_related('technicians', 'team')

    # 1. BY STAFF (INDIVIDUAL TECHNICIANS)
    technicians = Technician.objects.select_related('team').all()
    tech_stats = []

    for tech in technicians:
        target_day = tech.target_per_day if tech.target_per_day > 0 else 5
        target_month = tech.target_per_month if tech.target_per_month > 0 else 100
        scaled_target = target_month * months_count

        # Tech tickets
        tech_tickets = tickets_qs.filter(technicians=tech)
        installs = tech_tickets.exclude(ticket_type='REPAIR').count()
        repairs = tech_tickets.filter(ticket_type='REPAIR').count()
        total = installs + repairs

        pct_product = round((total / scaled_target) * 100.0, 1) if scaled_target > 0 else 0.0
        per_day_avg = round(total / working_days, 2) if working_days > 0 else 0.0

        tech_stats.append({
            'technician': tech,
            'name': tech.name,
            'team_name': tech.team.name if tech.team else 'Unassigned',
            'target_day': target_day,
            'target_month': target_month,
            'installs': installs,
            'repairs': repairs,
            'total': total,
            'pct_product': pct_product,
            'per_day_avg': per_day_avg,
        })

    tech_stats.sort(key=lambda x: (x['total'], x['pct_product']), reverse=True)

    # 2. BY TEAM (FIELD TEAMS)
    teams = Team.objects.prefetch_related('members').all()
    team_stats = []

    for team in teams:
        members = team.members.all()
        target_day = sum(m.target_per_day if m.target_per_day > 0 else 5 for m in members) or 10
        target_month = sum(m.target_per_month if m.target_per_month > 0 else 100 for m in members) or 200
        scaled_target = target_month * months_count

        team_tickets = tickets_qs.filter(Q(team=team) | Q(technicians__team=team)).distinct()
        installs = team_tickets.exclude(ticket_type='REPAIR').count()
        repairs = team_tickets.filter(ticket_type='REPAIR').count()
        total = installs + repairs

        pct_product = round((total / scaled_target) * 100.0, 1) if scaled_target > 0 else 0.0
        per_day_avg = round(total / working_days, 2) if working_days > 0 else 0.0

        team_stats.append({
            'team': team,
            'name': team.name,
            'member_count': members.count(),
            'target_day': target_day,
            'target_month': target_month,
            'installs': installs,
            'repairs': repairs,
            'total': total,
            'pct_product': pct_product,
            'per_day_avg': per_day_avg,
        })

    team_stats.sort(key=lambda x: (x['total'], x['pct_product']), reverse=True)

    return {
        'by_staff': tech_stats,
        'by_team': team_stats,
        'working_days': working_days,
        'months_count': months_count,
    }
