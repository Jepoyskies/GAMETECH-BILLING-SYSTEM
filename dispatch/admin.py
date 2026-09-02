from django.contrib import admin
from .models import Team, Technician, ConfigOption, DispatchRecord, MonitoringRecord, JobDetail, AuditLog

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
