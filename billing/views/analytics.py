from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from billing.decorators import role_required
from billing.models import Customer, SubscriptionPlan
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

@login_required
@role_required(['Admin', 'Superadmin'])
def analytics_dashboard(request):
    # Total Active Customers
    active_customers = Customer.objects.filter(status='active').count()
    
    # Monthly Recurring Revenue (MRR) - Sum of all active plans prices
    mrr = Customer.objects.filter(status='active', plan__isnull=False).aggregate(total_mrr=Sum('plan__price'))['total_mrr'] or 0
    
    # Churn Rate proxy - Users who were suspended or inactive
    churned_customers = Customer.objects.filter(status__in=['suspended', 'inactive']).count()
    
    # Plan distribution for Chart
    plan_distribution = list(SubscriptionPlan.objects.annotate(
        user_count=Count('customer', filter=Q(customer__status='active'))
    ).values('name', 'user_count'))

    # Recent signups (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_signups = Customer.objects.filter(created_at__gte=thirty_days_ago).count()

    context = {
        'active_customers': active_customers,
        'mrr': mrr,
        'churned_customers': churned_customers,
        'recent_signups': recent_signups,
        'plan_distribution': plan_distribution,
    }
    
    return render(request, 'billing/analytics.html', context)
