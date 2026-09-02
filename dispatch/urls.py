from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dispatch_dashboard'),
    path('monitoring/', views.dispatch_monitoring_view, name='dispatch_monitoring'),
    path('internet-install/', views.internet_install_view, name='internet_install'),
    path('cignal-install/', views.cignal_install_view, name='cignal_install'),
    path('client-concerns/', views.client_concerns_view, name='client_concerns'),
    path('complete-job/<int:record_id>/', views.complete_job_view, name='complete_job'),
    path('audit-log/', views.audit_log_view, name='audit_log'),
    path('management/', views.management_view, name='dispatch_management'),
]
