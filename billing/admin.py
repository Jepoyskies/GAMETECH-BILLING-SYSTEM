from django.contrib import admin
from .models import (
    AccountType, Customer, Agent, Barangay, Payment, JobOrder, AddonPlan,
    ChecklistPolicySetting, CommissionTransaction, StaffRole, SystemAdmin,
    Rebate, SmsLog, CignalPlay, AuditLog, EmployeeProfile, AddOnRequest,
    Notification, ImprovementRequest, MonitoredService, MessageTemplate,
    CustomerAgentHistory, Prospect, ChecklistConfirmation, AgentPayoutBatch,
    AgentQualificationEvent, IncentiveSetting,
)


# Helpers for RBAC
def is_in_group(user, group_name):
    if user.is_superuser:
        return True  # Superusers should ideally pass any group check conceptually in admin, or we handle it explicitly.
    return user.groups.filter(name=group_name).exists()


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ("type_name",)
    search_fields = ("type_name",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "plan", "status", "mikrotik_device")
    search_fields = ("full_name", "email", "phone", "mac_address")
    list_filter = ("status", "plan", "account_type", "mikrotik_device")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if is_in_group(request.user, "Agent"):
            # Agents only see their own customers
            return qs.filter(agent__user=request.user)
        # Technicians and CSRs can see all customers
        return qs

    def get_exclude(self, request, obj=None):
        if not request.user.is_superuser and is_in_group(request.user, "Technician"):
            return ["outstanding_balance", "plan", "payment_method", "amount"]
        return super().get_exclude(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_readonly_fields(request, obj)

        if is_in_group(request.user, "Agent"):
            # Agents can only edit basic info before activation maybe? Or just read only if already active.
            # For simplicity based on RBAC plan, they can view/edit own.
            pass

        if is_in_group(request.user, "Technician"):
            # Technicians shouldn't edit customer details, only JobOrders
            return [f.name for f in self.model._meta.fields]

        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False  # Nobody except Admin can delete customers
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            if obj.installation_status == "installed":
                if not (request.user.has_perm("billing.add_existing_subscriber") or request.user.is_superuser):
                    from django.core.exceptions import PermissionDenied
                    raise PermissionDenied("Permission denied: 'billing.add_existing_subscriber' required for manual override.")
                obj._checklist_verified = True
                super().save_model(request, obj, form, change)
                from billing.models import SystemLog
                try:
                    SystemLog.objects.create(
                        table_name="Customer",
                        record_id=str(obj.id),
                        action="MANUAL_OVERRIDE_ADMIN",
                        changed_by=request.user.username,
                        target_name=obj.full_name,
                        old_data="",
                        new_data=f"Created via Django Admin with override. Status: {obj.status}, Installation: {obj.installation_status}",
                    )
                except Exception:
                    pass
                return
        super().save_model(request, obj, form, change)


@admin.register(ChecklistPolicySetting)
class ChecklistPolicySettingAdmin(admin.ModelAdmin):
    list_display = ("version", "item_free_install_text", "item_no_lockin_text", "item_same_day_repair_text", "item_rebates_24h_text", "updated_at")
    ordering = ("-version",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("customer", "amount", "payment_method", "paid_at")
    search_fields = ("customer__full_name", "reference_no")
    list_filter = ("payment_method", "paid_at")

    def has_module_permission(self, request):
        if is_in_group(request.user, "Technician") or is_in_group(
            request.user, "Agent"
        ):
            return False
        return super().has_module_permission(request)

    def has_add_permission(self, request):
        # Only Admins can add payments manually, or maybe CSRs if permitted later
        if not request.user.is_superuser:
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(JobOrder)
class JobOrderAdmin(admin.ModelAdmin):
    list_display = ("job_type", "customer", "technician", "status", "created_at")
    list_filter = ("status", "job_type", "technician")
    search_fields = ("customer__full_name", "reported_issue")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or is_in_group(request.user, "CSR"):
            return qs
        if is_in_group(request.user, "Technician"):
            return qs.filter(technician=request.user)
        return qs.none()  # Agents shouldn't see Job Orders

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []
        if is_in_group(request.user, "Technician"):
            # Technicians can only update status, resolution_notes, start/end time
            return [
                "customer",
                "technician",
                "job_type",
                "reported_issue",
                "created_by",
            ]
        return []

    def has_add_permission(self, request):
        if is_in_group(request.user, "Technician") or is_in_group(
            request.user, "Agent"
        ):
            return False
        return True  # CSR and Admin can add

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "user")
    search_fields = ("name", "email")

    def has_module_permission(self, request):
        if not request.user.is_superuser:
            return False
        return super().has_module_permission(request)


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

    def has_module_permission(self, request):
        if not request.user.is_superuser:
            return False
        return super().has_module_permission(request)


@admin.register(AddonPlan)
class AddonPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "addon_type", "duration_days", "price", "is_active", "created_at")
    list_filter = ("addon_type", "is_active")
    search_fields = ("name", "description")


# ─── Operational / Audit Models (read-only staff visibility) ────────────────────

@admin.register(Rebate)
class RebateAdmin(admin.ModelAdmin):
    list_display = ("username", "plan_name", "amount", "days", "note", "adjusted_by", "created_at")
    list_filter = ("adjusted_by",)
    search_fields = ("username", "plan_name", "note")
    date_hierarchy = "created_at"


@admin.register(SmsLog)
class SmsLogAdmin(admin.ModelAdmin):
    list_display = ("phone", "message", "status", "sent_at")
    list_filter = ("status",)
    search_fields = ("phone", "message")
    date_hierarchy = "sent_at"


@admin.register(CignalPlay)
class CignalPlayAdmin(admin.ModelAdmin):
    list_display = ("customer", "cignal_play_no", "cignal_box_no", "account_name", "plan_name",
                    "start_date", "expiration_date", "is_cancelled", "cancelled_by")
    list_filter = ("is_cancelled", "plan_name")
    search_fields = ("customer__full_name", "cignal_play_no", "cignal_box_no", "account_name")
    date_hierarchy = "start_date"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action_type", "admin_user", "customer", "timestamp")
    list_filter = ("action_type",)
    search_fields = ("admin_user__username", "customer__full_name", "remarks")
    date_hierarchy = "timestamp"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "notification_type", "is_read", "created_at")
    list_filter = ("is_read", "notification_type")
    search_fields = ("title", "message")
    date_hierarchy = "created_at"


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "subject")
    list_filter = ("type",)
    search_fields = ("name", "subject", "body")


@admin.register(Prospect)
class ProspectAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "agent", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("full_name", "phone", "address")
    date_hierarchy = "created_at"


@admin.register(ChecklistConfirmation)
class ChecklistConfirmationAdmin(admin.ModelAdmin):
    list_display = ("customer", "prospect", "outcome", "method", "policy_version", "created_at")
    list_filter = ("outcome", "method", "policy_version")
    search_fields = ("customer__full_name", "applicant_name", "applicant_phone")


@admin.register(AgentPayoutBatch)
class AgentPayoutBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_number", "agent", "amount", "customer_count", "status", "created_at", "paid_at")
    list_filter = ("status",)
    search_fields = ("agent__name", "reference_no", "batch_number")
    date_hierarchy = "created_at"


@admin.register(AgentQualificationEvent)
class AgentQualificationEventAdmin(admin.ModelAdmin):
    list_display = ("agent", "customer", "qualifying_amount", "status", "qualified_at", "payout_batch")
    list_filter = ("status",)
    search_fields = ("agent__name", "customer__full_name")
    date_hierarchy = "qualified_at"


@admin.register(CommissionTransaction)
class CommissionTransactionAdmin(admin.ModelAdmin):
    list_display = ("agent", "customer", "amount", "status", "created_at", "paid_at")
    list_filter = ("status",)
    search_fields = ("agent__name", "customer__full_name")
    date_hierarchy = "created_at"


@admin.register(CustomerAgentHistory)
class CustomerAgentHistoryAdmin(admin.ModelAdmin):
    list_display = ("customer", "from_agent", "to_agent", "changed_by", "reason", "created_at")
    search_fields = ("customer__full_name", "reason")
    date_hierarchy = "created_at"


@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "can_access_billing", "can_access_network_ops", "can_access_cignal_play", "can_access_dispatch", "can_access_administration")
    list_filter = ("can_access_billing", "can_access_network_ops", "can_access_cignal_play", "can_access_dispatch", "can_access_administration")
    search_fields = ("name",)


@admin.register(SystemAdmin)
class SystemAdminAdmin(admin.ModelAdmin):
    list_display = ("username", "full_name", "email", "role", "status", "created_at")
    list_filter = ("role", "status")
    search_fields = ("username", "full_name", "email")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "employee_id", "phone_number", "branch_location")
    search_fields = ("user__username", "user__full_name", "employee_id")


@admin.register(AddOnRequest)
class AddOnRequestAdmin(admin.ModelAdmin):
    list_display = ("customer", "addon_type", "status", "requested_at")
    list_filter = ("status",)
    search_fields = ("customer__full_name",)


@admin.register(ImprovementRequest)
class ImprovementRequestAdmin(admin.ModelAdmin):
    list_display = ("submitted_by", "status", "created_at", "dev_note")
    list_filter = ("status",)
    search_fields = ("submitted_by__username", "message")


@admin.register(MonitoredService)
class MonitoredServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "service_type", "target", "status", "latency_ms", "last_checked")
    list_filter = ("status", "service_type")
    search_fields = ("name", "target")


@admin.register(IncentiveSetting)
class IncentiveSettingAdmin(admin.ModelAdmin):
    list_display = ("incentive_amount", "batch_size", "lock_days", "updated_at")

