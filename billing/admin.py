from django.contrib import admin
from .models import AccountType, ServicePlan, Customer

@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ('type_name',)
    search_fields = ('type_name',)

@admin.register(ServicePlan)
class ServicePlanAdmin(admin.ModelAdmin):
    list_display = ('plan_name', 'plan_code', 'speed_up', 'speed_down', 'price', 'validity_days')
    search_fields = ('plan_name', 'plan_code')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('username', 'full_name', 'email', 'phone', 'service_plan', 'status', 'mikrotik_device', 'expires_at')
    search_fields = ('username', 'full_name', 'email', 'phone', 'mac_address')
    list_filter = ('status', 'service_plan', 'account_type', 'mikrotik_device')
    autocomplete_fields = ('service_plan', 'account_type', 'mikrotik_device')
