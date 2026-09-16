from django.urls import path
from . import views

urlpatterns = [
    path('', views.dispatch_index_view, name='dispatch_index'),
    path('dashboard/', views.dashboard_view, name='dispatch_dashboard'),
    path('monitoring/', views.dispatch_monitoring_view, name='dispatch_monitoring'),
    path('internet-install/', views.internet_install_view, name='internet_install'),
    path('cignal-install/', views.cignal_install_view, name='cignal_install'),
    path('client-concerns/', views.client_concerns_view, name='client_concerns'),
    path('complete-job/<int:record_id>/', views.complete_job_view, name='complete_job'),
    path('audit-log/', views.audit_log_view, name='audit_log'),
    path('management/', views.management_view, name='dispatch_management'),

    # REST APIs for dynamic interactions & mobile tech view
    path('api/tickets/', views.api_tickets_list, name='api_dispatch_tickets'),
    path('api/tickets/create/', views.api_create_ticket, name='api_dispatch_create_ticket'),
    path('api/tickets/<int:ticket_id>/', views.api_ticket_detail, name='api_dispatch_ticket_detail'),
    path('api/tickets/<int:ticket_id>/assign/', views.api_assign_ticket, name='api_dispatch_assign_ticket'),
    path('api/tickets/<int:ticket_id>/status/', views.api_update_status, name='api_dispatch_update_status'),
    path('api/tickets/<int:ticket_id>/location/', views.api_update_location, name='api_dispatch_update_location'),
    path('api/tickets/<int:ticket_id>/complete/', views.api_complete_job, name='api_dispatch_complete_job'),
]
