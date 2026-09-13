from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q
from billing.models import Customer, CignalPlay, AddOnRequest, Notification

@login_required
def cignal_dashboard_view(request):
    today = timezone.localtime().date()
    
    # KPIs
    active_customers = Customer.objects.filter(
        (Q(cignalplay_no__isnull=False) & ~Q(cignalplay_no__exact=""))
        | (Q(cignalbox_no__isnull=False) & ~Q(cignalbox_no__exact=""))
    )
    
    active_cignal_customers = active_customers.count()
    
    pending_applications = AddOnRequest.objects.filter(
        Q(addon_type__icontains='Cignal') | Q(addon_type__icontains='Box'),
        status='Pending'
    )
    pending_applications_count = pending_applications.count()
    
    new_cignal_this_month = CignalPlay.objects.filter(
        created_at__month=today.month, 
        created_at__year=today.year
    ).count()

    total_notifications = Notification.objects.filter(notification_type='cignal').count()

    # Tables Data
    # 1. Customers List
    customers_list = active_customers.order_by('-cignalplay_date')[:15]
    
    # 2. Cignal Logs/Renewals (Payments equivalent)
    cignal_payments = CignalPlay.objects.all().select_related('customer').order_by('-created_at')[:15]
    
    # 3. Notifications/Messages
    notifications = Notification.objects.filter(notification_type='cignal').order_by('-id')[:10]

    context = {
        'active_cignal_customers': active_cignal_customers,
        'pending_applications_count': pending_applications_count,
        'new_cignal_this_month': new_cignal_this_month,
        'total_notifications': total_notifications,
        'customers_list': customers_list,
        'applications': pending_applications,
        'cignal_payments': cignal_payments,
        'notifications': notifications,
    }
    
    return render(request, "billing/cignal_dashboard.html", context)
