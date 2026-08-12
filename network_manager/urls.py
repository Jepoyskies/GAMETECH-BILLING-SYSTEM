from django.urls import path
from . import views

urlpatterns = [
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.add_device, name='add_device'),
    path('devices/edit/<int:device_id>/', views.edit_device, name='edit_device'),
    path('devices/delete/<int:device_id>/', views.delete_device, name='delete_device'),
    
    # This is for the "Test Connection" AJAX button!
    path('devices/test/<int:device_id>/', views.test_device_connection, name='test_device'),
]