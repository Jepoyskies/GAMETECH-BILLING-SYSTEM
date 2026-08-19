from django.urls import path
from . import views

app_name = 'customer_portal'

urlpatterns = [
    path('login/', views.portal_login, name='portal_login'),
    path('dashboard/', views.portal_dashboard, name='portal_dashboard'),
    path('logout/', views.portal_logout, name='portal_logout'),
]
