from django.urls import path
from . import views

app_name = 'customer_portal'

from django.views.generic import RedirectView

urlpatterns = [
    path('login/', RedirectView.as_view(url='/login/', permanent=False), name='portal_login'),
    path('dashboard/', views.portal_dashboard, name='portal_dashboard'),
    path('statement/', views.portal_statement_view, name='portal_statement'),
    path('process-mock-payment/', views.portal_process_mock_payment, name='portal_process_mock_payment'),
    path('api/router-uplink/', views.portal_router_uplink_api, name='portal_router_uplink_api'),
    path('api/apply-addon/', views.portal_apply_addon, name='portal_apply_addon'),
    path('logout/', views.portal_logout, name='portal_logout'),
]
