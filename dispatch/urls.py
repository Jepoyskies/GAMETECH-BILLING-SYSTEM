from django.urls import path
from . import views
from . import pipeline_views

urlpatterns = [
    path('', views.dispatch_index_view, name='dispatch_index'),
    path('dashboard/', views.dashboard_view, name='dispatch_dashboard'),
    path('monitoring/', views.dispatch_monitoring_view, name='dispatch_monitoring'),
    path('dispatches/', views.dispatch_monitoring_view, name='dispatch_dispatches'),
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
    path('api/records/<int:record_id>/delete/', views.api_delete_record, name='api_dispatch_delete_record'),
    path('api/tickets/<int:ticket_id>/contact-attempt/', views.api_log_contact_attempt, name='api_dispatch_contact_attempt'),
    path('api/tickets/<int:ticket_id>/mark-unreachable/', views.api_mark_unreachable, name='api_dispatch_mark_unreachable'),
    path('api/tickets/<int:ticket_id>/send-welcome-sms/', views.api_send_welcome_sms, name='api_dispatch_send_welcome_sms'),
    
    # Phase 3: Customer search & duplicate check APIs
    path('api/customers/search/', views.api_customer_search, name='api_dispatch_customer_search'),
    path('api/customers/check-name/', views.api_customer_check_name, name='api_dispatch_customer_check_name'),

    # Phase 3: Dynamic Dropdown Config APIs
    path('api/config-options/create/', views.api_config_options_create, name='api_dispatch_config_options_create'),
    path('api/config-options/<int:option_id>/update/', views.api_config_options_update, name='api_dispatch_config_options_update'),
    path('api/config-options/<int:option_id>/delete/', views.api_config_options_delete, name='api_dispatch_config_options_delete'),

    # Phase 4: Management APIs (Teams, Technicians, Targets)
    path('api/teams/create/', views.api_team_create, name='api_dispatch_team_create'),
    path('api/teams/<int:team_id>/update/', views.api_team_update, name='api_dispatch_team_update'),
    path('api/teams/<int:team_id>/delete/', views.api_team_delete, name='api_dispatch_team_delete'),
    path('api/technicians/create/', views.api_technician_create, name='api_dispatch_technician_create'),
    path('api/technicians/<int:tech_id>/update/', views.api_technician_update, name='api_dispatch_technician_update'),
    path('api/technicians/<int:tech_id>/delete/', views.api_technician_delete, name='api_dispatch_technician_delete'),
    path('api/technicians/<int:tech_id>/targets/', views.api_technician_targets_update, name='api_dispatch_technician_targets_update'),

    path('export/tickets/', views.export_tickets_csv, name='dispatch_export_tickets'),

    # Official Printable ISP Job Order Form (Installation / Repair Service)
    path('tickets/<int:ticket_id>/job-order/', views.job_order_print_view, name='dispatch_job_order_print'),
    path('job-order/blank/', views.job_order_print_view, name='dispatch_job_order_blank'),
    path('records/<int:record_id>/job-order/', views.job_order_print_record_view, name='dispatch_job_order_print_record'),
]
