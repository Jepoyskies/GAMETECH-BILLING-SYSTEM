from django.contrib import admin
from .models import AccountType, ServicePlan, Customer, Agent, Barangay


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ('type_name',)
    search_fields = ('type_name',)


@admin.register(ServicePlan)
class ServicePlanAdmin(admin.ModelAdmin):
    list_display = ('plan_name', 'plan_code', 'speed_up',
                    'speed_down', 'price', 'validity_days')
    search_fields = ('plan_name', 'plan_code')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone',
                    'plan', 'status', 'mikrotik_device')
    search_fields = ('full_name', 'email', 'phone', 'mac_address')
    list_filter = ('status', 'plan', 'account_type', 'mikrotik_device')


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone')
    search_fields = ('name', 'email')


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
