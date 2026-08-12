from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Dashboard route
    path('', views.dashboard_view, name='dashboard'),

    # Customer routes
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/edit/<int:customer_id>/',
         views.edit_customer, name='edit_customer'),
    path('customers/view/<int:customer_id>/',
         views.view_customer, name='view_customer'),
    path('customers/delete/<int:customer_id>/',
         views.delete_customer, name='delete_customer'),
    path('mikrotik-active-users/', views.mikrotik_active_users_view,
         name='mikrotik_active_users'),

    # Live Monitoring routes
    path('live-monitoring/', views.live_monitoring_view, name='live_monitoring'),
    path('api/live-monitoring/', views.api_live_monitoring_data,
         name='api_live_monitoring'),

    # Subscription / Service Plans routes
    path('subscriptions/', views.subscription_plans_view,
         name='subscription_plans'),
    # Payments
    path('payments/', views.payment_logs_view, name='payment_logs'),
    path('payments/pay/<int:customer_id>/',
         views.create_payment_view, name='pay_customer'),

    # Auth route
    path('login/', auth_views.LoginView.as_view(template_name='billing/login.html'), name='login'),
    path('agents/', views.agent_list, name='agent_list'),
    path('agents/add/', views.add_agent, name='add_agent'),
    path('agents/edit/<int:agent_id>/', views.edit_agent, name='edit_agent'),
    path('agents/view/<int:agent_id>/', views.view_agent, name='view_agent'),
    path('agents/delete/<int:agent_id>/',
         views.delete_agent, name='delete_agent'),
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/add/', views.add_plan, name='add_plan'),
    path('plans/edit/<int:plan_id>/', views.edit_plan, name='edit_plan'),
    path('plans/delete/<int:plan_id>/', views.delete_plan, name='delete_plan'),
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.add_staff, name='add_staff'),
]
