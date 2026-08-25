from django.urls import path
from . import views

urlpatterns = [
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.add_device, name='add_device'),
    path('devices/edit/<int:device_id>/',
         views.edit_device, name='edit_device'),
    path('devices/delete/<int:device_id>/',
         views.delete_device, name='delete_device'),

    # This is for the "Test Connection" AJAX button!
    path('devices/<int:device_id>/test/', views.test_device_connection, name='test_device'),
    path('devices/<int:device_id>/setup-profiles/', views.setup_router_profiles, name='setup_router_profiles'),
    path('devices/<int:device_id>/sync-users/', views.sync_device_users, name='sync_device_users'),
    path('devices/<int:device_id>/sync/', views.sync_manager, name='sync_manager'),
    path('devices/<int:device_id>/sync/push/', views.sync_push_user, name='sync_push_user'),
    path('devices/<int:device_id>/sync/delete/', views.sync_delete_user, name='sync_delete_user'),
    path('devices/<int:device_id>/sync/bulk/', views.sync_bulk_action, name='sync_bulk_action'),
    path('devices/hardware/<int:device_id>/',
         views.device_hardware_api, name='device_hardware_api'),
         
    # NAP Box URLs
    path('napboxes/', views.nap_list_view, name='nap_list'),
    path('napboxes/add/', views.add_nap_view, name='add_nap'),
    path('napboxes/edit/<int:nap_id>/', views.edit_nap_view, name='edit_nap'),
    path('napboxes/delete/<int:nap_id>/', views.delete_nap_view, name='delete_nap'),
    path('tools/calculator/', views.fbt_plc_calculator_view, name='fbt_plc_calculator'),
]
