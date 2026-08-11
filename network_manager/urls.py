from django.urls import path
from . import views

urlpatterns = [
    path('', views.device_list_view, name='device_list'),
    path('add/', views.add_device_view, name='add_device'),
    path('edit/<int:device_id>/', views.edit_device_view, name='edit_device'),
    path('delete/<int:device_id>/', views.delete_device_view, name='delete_device'),
    path('test-connection/<int:device_id>/', views.test_connection_view, name='test_connection'),
]
