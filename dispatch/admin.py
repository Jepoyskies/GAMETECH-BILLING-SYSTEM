from django.contrib import admin
from .models import (
    Team, Technician, ConfigOption, DispatchRecord, MonitoringRecord,
    JobDetail, AuditLog, JobTicket, JobTicketHistory,
    TicketBounceHistory, CallAttemptLog
)

@admin.register(JobTicket)
class JobTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'client_name', 'ticket_type', 'status', 'priority', 'scheduled_date', 'created_at')
    list_filter = ('status', 'ticket_type', 'priority', 'source_tab', 'scheduled_date')
    search_fields = ('ticket_number', 'client_name', 'contact_number', 'account_no', 'address')
    date_hierarchy = 'created_at'

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_number', 'team', 'target_per_day')
    search_fields = ('name', 'contact_number')
    list_filter = ('team',)

@admin.register(ConfigOption)
class ConfigOptionAdmin(admin.ModelAdmin):
    list_display = ('label', 'list_type', 'module', 'active', 'color')
    list_filter = ('list_type', 'module', 'active')
    search_fields = ('label',)

@admin.register(DispatchRecord)
class DispatchRecordAdmin(admin.ModelAdmin):
    list_display = ('date', 'client_name', 'source_tab', 'status_option')
    list_filter = ('source_tab', 'status_option', 'date')
    search_fields = ('client_name', 'address', 'ticket_number')
    date_hierarchy = 'date'

@admin.register(MonitoringRecord)
class MonitoringRecordAdmin(admin.ModelAdmin):
    list_display = ('date', 'client_name', 'tab_type', 'status_option')
    list_filter = ('tab_type', 'status_option', 'date')
    search_fields = ('client_name', 'address', 'ticket_number')
    date_hierarchy = 'date'

@admin.register(JobDetail)
class JobDetailAdmin(admin.ModelAdmin):
    list_display = ('record', 'schedule_date', 'plan_package', 'job_order')
    search_fields = ('account_no', 'job_order', 'email_address')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'entity_type', 'entity_id', 'actor', 'created_at')
    list_filter = ('action', 'entity_type')
    search_fields = ('summary', 'actor__username')

@admin.register(JobTicketHistory)
class JobTicketHistoryAdmin(admin.ModelAdmin):
    list_display = ('job_ticket', 'actor', 'from_status', 'to_status', 'timestamp')
    list_filter = ('to_status', 'timestamp')
    search_fields = ('job_ticket__ticket_number',)
    date_hierarchy = 'timestamp'

@admin.register(TicketBounceHistory)
class TicketBounceHistoryAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'from_stage', 'to_stage', 'bounce_type', 'bounced_by', 'created_at')
    list_filter = ('bounce_type', 'from_stage', 'to_stage')
    search_fields = ('ticket__ticket_number', 'reason')
    date_hierarchy = 'created_at'

@admin.register(CallAttemptLog)
class CallAttemptLogAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'technician', 'attempt_number', 'result', 'attempt_time')
    list_filter = ('result', 'attempt_number')
    search_fields = ('ticket__ticket_number',)

