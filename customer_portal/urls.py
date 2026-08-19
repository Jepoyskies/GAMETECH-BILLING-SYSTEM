from django.urls import path
from . import views

app_name = 'customer_portal'

from django.views.generic import RedirectView

urlpatterns = [
    path('login/', RedirectView.as_view(url='/login/', permanent=False), name='portal_login'),
    path('dashboard/', views.portal_dashboard, name='portal_dashboard'),
    path('api/router-uplink/', views.portal_router_uplink_api, name='portal_router_uplink_api'),
    path('logout/', views.portal_logout, name='portal_logout'),
]
