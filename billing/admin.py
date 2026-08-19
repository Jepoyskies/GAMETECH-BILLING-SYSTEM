from django.contrib import admin
from .models import AccountType, Customer, Agent, Barangay, Payment

# Helpers for RBAC
def is_in_group(user, group_name):
    if user.is_superuser:
        return False
    return user.groups.filter(name=group_name).exists()

class BaseRBACAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        if is_in_group(request.user, 'Agent'):
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if is_in_group(request.user, 'Agent'):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if is_in_group(request.user, 'Agent'):
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if is_in_group(request.user, 'Agent'):
            return [f.name for f in self.model._meta.fields]
        return super().get_readonly_fields(request, obj)

@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ('type_name',)
    search_fields = ('type_name',)


@admin.register(Customer)
class CustomerAdmin(BaseRBACAdmin):
    list_display = ('full_name', 'email', 'phone',
                    'plan', 'status', 'mikrotik_device')
    search_fields = ('full_name', 'email', 'phone', 'mac_address')
    list_filter = ('status', 'plan', 'account_type', 'mikrotik_device')

    def get_exclude(self, request, obj=None):
        if is_in_group(request.user, 'Technician'):
            return ['outstanding_balance', 'plan']
        return super().get_exclude(request, obj)

@admin.register(Payment)
class PaymentAdmin(BaseRBACAdmin):
    list_display = ('customer', 'amount', 'payment_method', 'paid_at')
    search_fields = ('customer__full_name', 'reference_no')
    list_filter = ('payment_method', 'paid_at')


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone')
    search_fields = ('name', 'email')


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
