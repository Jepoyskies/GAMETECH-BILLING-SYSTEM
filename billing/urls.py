from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Dashboard route
    path('', views.dashboard_view, name='dashboard'),
    
    # Customer routes
    path('add-customer/', views.add_customer_view, name='add_customer'),
    path('mikrotik-active-users/', views.mikrotik_active_users_view, name='mikrotik_active_users'),
    
    # Live Monitoring routes
    path('live-monitoring/', views.live_monitoring_view, name='live_monitoring'),
    path('api/live-monitoring/', views.api_live_monitoring_data, name='api_live_monitoring'),
    
    # Auth route
    path('login/', auth_views.LoginView.as_view(template_name='billing/login.html'), name='login'),
    path('agents/', views.agent_list, name='agent_list'),
    path('agents/add/', views.add_agent, name='add_agent'),
    path('agents/edit/<int:agent_id>/', views.edit_agent, name='edit_agent'),
    path('agents/view/<int:agent_id>/', views.view_agent, name='view_agent'),
    path('agents/delete/<int:agent_id>/', views.delete_agent, name='delete_agent'),
]
