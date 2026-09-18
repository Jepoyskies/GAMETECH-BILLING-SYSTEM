from django.urls import path
from . import views
from . import pipeline_views

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
    
    # 5-Stage ERP Pipeline
    path('pipeline/1-verification/', pipeline_views.dispatch_verification, name='dispatch_verification'),
    path('pipeline/2-assignment/', pipeline_views.dispatch_assignment, name='dispatch_assignment'),
    path('pipeline/2-assignment/undispatch/<int:ticket_id>/', pipeline_views.dispatch_undispatch, name='dispatch_undispatch'),
    path('pipeline/3-mobile-tech/', pipeline_views.technician_mobile_ui, name='technician_mobile_ui'),
    path('pipeline/4-qa/', pipeline_views.dispatch_qa, name='dispatch_qa'),
    path('pipeline/5-approval/', pipeline_views.dispatch_approval, name='dispatch_approval'),

    # REST APIs for dynamic interactions & mobile tech view
    path('api/tickets/', views.api_tickets_list, name='api_dispatch_tickets'),
    path('api/tickets/create/', views.api_create_ticket, name='api_dispatch_create_ticket'),
    path('api/tickets/<int:ticket_id>/', views.api_ticket_detail, name='api_dispatch_ticket_detail'),
    path('api/tickets/<int:ticket_id>/assign/', views.api_assign_ticket, name='api_dispatch_assign_ticket'),
    path('api/tickets/<int:ticket_id>/status/', views.api_update_status, name='api_dispatch_update_status'),
    path('api/tickets/<int:ticket_id>/undispatch/', views.api_undispatch_ticket, name='api_dispatch_undispatch_ticket'),
    path('api/tickets/<int:ticket_id>/location/', views.api_update_location, name='api_dispatch_update_location'),
    path('api/tickets/<int:ticket_id>/complete/', views.api_complete_job, name='api_dispatch_complete_job'),
    path('api/tickets/<int:ticket_id>/delete/', views.api_delete_ticket, name='api_dispatch_delete_ticket'),
    path('export/tickets/', views.export_tickets_csv, name='dispatch_export_tickets'),
]
