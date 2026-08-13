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
    path('devices/test/<int:device_id>/',
         views.test_device_connection, name='test_device'),
    path('devices/sync/<int:device_id>/',
         views.sync_device_users, name='sync_device_users'),
    path('devices/hardware/<int:device_id>/',
         views.device_hardware_api, name='device_hardware_api'),
         
    # NAP Box URLs
    path('napboxes/', views.nap_list_view, name='nap_list'),
    path('napboxes/add/', views.add_nap_view, name='add_nap'),
    path('napboxes/edit/<int:nap_id>/', views.edit_nap_view, name='edit_nap'),
    path('napboxes/delete/<int:nap_id>/', views.delete_nap_view, name='delete_nap'),
    path('tools/calculator/', views.fbt_plc_calculator_view, name='fbt_plc_calculator'),
]
