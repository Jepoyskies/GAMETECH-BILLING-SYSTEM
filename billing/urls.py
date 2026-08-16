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
    path('customer/force-suspend/<str:username>/', 
         views.customer_force_suspend, name='customer_force_suspend'),
    path('customer/kick-session/<str:username>/', 
         views.customer_kick_session, name='customer_kick_session'),
    path('customer/force-reactivate/<str:username>/', 
         views.customer_force_reactivate, name='customer_force_reactivate'),
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
    # (payments/ path removed since we use logs/payments/ below)
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
    path('plans/sync/', views.sync_plans_from_mikrotik, name='sync_plans_from_mikrotik'),
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/add/', views.add_staff, name='add_staff'),
    path('staff/edit/<int:pk>/', views.edit_staff, name='edit_staff'),

    # Core UI & Placeholders
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    path('admin-panel/', views.admin_panel_view, name='admin_panel'),
    
    # Auth Extensions
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('change-password/', auth_views.PasswordChangeView.as_view(
        template_name='billing/change_password.html',
        success_url='/profile/?password_changed=1'
    ), name='change_password'),

    # Logs route
    path('logs/', views.system_logs_view, name='system_logs'),

    # Geo Map routes
    path('geomap/', views.geomap_view, name='geomap'),
    path('geomap/save/', views.save_marker_positions, name='save_marker_positions'),

    # MAC History
    path('mac-history/', views.mac_history_view, name='mac_history'),
    # Financial Engine: Rebates & Rollbacks
    path('customer/<str:username>/rebate/', views.customer_rebate_view, name='customer_rebate'),
    path('customer/<str:username>/rollback/', views.customer_rollback_view, name='customer_rollback'),
    path('payment/success/', views.payment_success_view, name='payment_success'),
    path('logs/payments/', views.payment_logs_view, name='payment_logs'),
    path('logs/payment-addons/', views.payment_addon_logs_view, name='payment_addon_logs'),
    # Payment Processing
    path('payment-portal/', views.payment_portal_view, name='payment_portal'),
    path('customer/<str:username>/pay/', views.pay_customer_view, name='pay_customer'),
    path('logs/rebates/', views.rebates_logs_view, name='rebates_logs'),
    
    path('auto-suspend/', views.auto_suspend_view, name='auto_suspend'),
    path('sms/', views.sms_view, name='sms_messaging'),
    
    # Cignal Play Integration
    path('cignal-play/', views.cignal_play_list_view, name='cignal_play_list'),
    path('add-ons/', views.add_on_payments_view, name='add_on_payments'),
    path('customer/<int:customer_id>/cignalplay-form/', views.cignalplay_form_view, name='cignalplay_form'),
    path('customer/<int:customer_id>/cignal-logs/', views.user_cignal_logs_view, name='user_cignal_logs'),
    
    path('customer/<int:customer_id>/soa/', views.statement_of_account_view, name='statement_of_account'),
    
    # Master Data Management (Settings)
    path('settings/account-types/', views.account_type_list, name='account_type_list'),
    path('settings/account-types/add/', views.create_account_type, name='create_account_type'),
    path('settings/account-types/edit/<int:pk>/', views.edit_account_type, name='edit_account_type'),
    path('settings/account-types/delete/<int:pk>/', views.delete_account_type, name='delete_account_type'),
    
    path('settings/barangays/', views.barangay_list, name='barangay_list'),
    path('settings/barangays/add/', views.create_barangay, name='create_barangay'),
    path('settings/barangays/edit/<int:pk>/', views.edit_barangay, name='edit_barangay'),
    path('settings/barangays/delete/<int:pk>/', views.delete_barangay, name='delete_barangay'),
    
    path('settings/backup/', views.backup_database_view, name='backup_database'),
]
