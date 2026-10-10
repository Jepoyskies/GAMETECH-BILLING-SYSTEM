from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from billing.models import Customer, Agent

from .core import ConfigOption, Technician


class DispatchRecord(models.Model):
    SOURCE_TAB_CHOICES = (
        ('INTERNET_INSTALL', 'INTERNET_INSTALL'),
        ('CIGNAL_PLAY', 'CIGNAL_PLAY'),
        ('CLIENT_CONCERNS', 'CLIENT_CONCERNS'),
    )
    date = models.DateField(default=timezone.now)
    client_name = models.CharField(max_length=255)
    address = models.TextField()
    contact_number = models.CharField(max_length=50)
    alternate_contact = models.CharField(max_length=150, null=True, blank=True)
    facebook_account = models.CharField(max_length=255, null=True, blank=True)
    concern = models.TextField()
    sales_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatch_records')
    is_test_data = models.BooleanField(default=False, help_text="Flags test dispatch records")

    chat_type_option = models.ForeignKey(ConfigOption, on_delete=models.RESTRICT, related_name='dispatch_chat_types', null=True, blank=True)
    type_option = models.ForeignKey(ConfigOption, on_delete=models.RESTRICT, related_name='dispatch_types', null=True, blank=True)
    status_option = models.ForeignKey(ConfigOption, on_delete=models.RESTRICT, related_name='dispatch_statuses', null=True, blank=True)

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)

    time_start = models.DateTimeField(null=True, blank=True)
    time_accomplish = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True, help_text="Duration in minutes")

    done_at = models.DateTimeField(null=True, blank=True)
    done_duration = models.IntegerField(null=True, blank=True)

    source_tab = models.CharField(max_length=30, choices=SOURCE_TAB_CHOICES)
    ticket_number = models.CharField(max_length=100, null=True, blank=True)
    actions_taken = models.TextField(null=True, blank=True)

    sla_rebates_given = models.IntegerField(default=0, help_text="Number of 24h SLA rebate days automatically given")

    # Link to the MonitoringRecord that auto-created this dispatch (if applicable)
    monitoring_record = models.OneToOneField('MonitoringRecord', on_delete=models.SET_NULL, null=True, blank=True, related_name='auto_dispatch_source')

    # Job detail fields (copied from MonitoringRecord's JobDetail on auto-dispatch)
    schedule_date = models.DateField(null=True, blank=True)
    schedule_time = models.CharField(max_length=100, null=True, blank=True)
    barangay_city = models.CharField(max_length=100, null=True, blank=True)
    account_no = models.CharField(max_length=100, null=True, blank=True)
    job_order = models.CharField(max_length=100, null=True, blank=True)
    email_address = models.EmailField(null=True, blank=True)
    nap_port = models.CharField(max_length=100, null=True, blank=True)
    cable_length = models.CharField(max_length=100, null=True, blank=True)
    nap_reading = models.CharField(max_length=100, null=True, blank=True)
    pole_number = models.CharField(max_length=100, null=True, blank=True)
    plan_package = models.CharField(max_length=100, null=True, blank=True)
    ont_modem_sn = models.CharField(max_length=100, null=True, blank=True)
    signal_level = models.CharField(max_length=100, null=True, blank=True)
    facility = models.CharField(max_length=100, null=True, blank=True)
    house_reading = models.CharField(max_length=100, null=True, blank=True)
    special_instruction = models.TextField(null=True, blank=True)
    technician_remarks = models.TextField(null=True, blank=True)
    acknowledged_by = models.CharField(max_length=100, null=True, blank=True)

    teams = models.ManyToManyField(Technician, related_name='dispatches')
    csr = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='handled_dispatches')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatches')
    mikrotik_device = models.ForeignKey('network_manager.MikrotikDevice', on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatches')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.client_name} - {self.source_tab}"


class MonitoringRecord(models.Model):
    SOURCE_TAB_CHOICES = (
        ('INTERNET_INSTALL', 'INTERNET_INSTALL'),
        ('CIGNAL_PLAY', 'CIGNAL_PLAY'),
        ('CLIENT_CONCERNS', 'CLIENT_CONCERNS'),
    )
    tab_type = models.CharField(max_length=30, choices=SOURCE_TAB_CHOICES)
    date = models.DateField(default=timezone.now)
    client_name = models.CharField(max_length=255)
    address = models.TextField()
    contact_number = models.CharField(max_length=50)
    alternate_contact = models.CharField(max_length=150, null=True, blank=True)
    facebook_account = models.CharField(max_length=255, null=True, blank=True)
    concern = models.TextField()
    sales_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='monitoring_records')
    is_test_data = models.BooleanField(default=False, help_text="Flags test monitoring records")

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    status_option = models.ForeignKey(ConfigOption, on_delete=models.RESTRICT, related_name='monitoring_statuses', null=True, blank=True)
    type_option = models.ForeignKey(ConfigOption, on_delete=models.RESTRICT, related_name='monitoring_types', null=True, blank=True)
    chat_type_option = models.ForeignKey(ConfigOption, on_delete=models.RESTRICT, related_name='monitoring_chat_types', null=True, blank=True)

    remarks = models.TextField(null=True, blank=True)
    ticket_number = models.CharField(max_length=100, null=True, blank=True)
    actions_taken = models.TextField(null=True, blank=True)

    time_start = models.DateTimeField(null=True, blank=True)
    time_accomplish = models.DateTimeField(null=True, blank=True)

    done_at = models.DateTimeField(null=True, blank=True)
    done_duration = models.IntegerField(null=True, blank=True)

    teams = models.ManyToManyField(Technician, related_name='monitoring_records')
    dispatch = models.OneToOneField(DispatchRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatch_record')
    csr = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='handled_monitoring_records')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='monitoring_records')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.client_name} - {self.tab_type}"


class JobDetail(models.Model):
    record = models.OneToOneField(MonitoringRecord, on_delete=models.CASCADE, related_name='job_detail')

    # Pending / Assignment fields
    schedule_date = models.DateField(null=True, blank=True)
    schedule_time = models.CharField(max_length=100, null=True, blank=True)
    barangay_city = models.CharField(max_length=100, null=True, blank=True)
    account_no = models.CharField(max_length=100, null=True, blank=True)
    job_order = models.CharField(max_length=100, null=True, blank=True)
    email_address = models.EmailField(null=True, blank=True)

    # Completion fields
    nap_port = models.CharField(max_length=100, null=True, blank=True)
    cable_length = models.CharField(max_length=100, null=True, blank=True)
    nap_reading = models.CharField(max_length=100, null=True, blank=True)
    pole_number = models.CharField(max_length=100, null=True, blank=True)
    plan_package = models.CharField(max_length=100, null=True, blank=True)
    ont_modem_sn = models.CharField(max_length=100, null=True, blank=True)
    signal_level = models.CharField(max_length=100, null=True, blank=True)
    facility = models.CharField(max_length=100, null=True, blank=True)
    house_reading = models.CharField(max_length=100, null=True, blank=True)
    special_instruction = models.TextField(null=True, blank=True)

    # Post-completion fields
    technician_remarks = models.TextField(null=True, blank=True)
    acknowledged_by = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job Detail for {self.record}"


class AuditLog(models.Model):
    ACTION_CHOICES = (
        ('CREATE', 'CREATE'),
        ('UPDATE', 'UPDATE'),
        ('DELETE', 'DELETE'),
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=100)  # e.g. "DispatchRecord", "MonitoringRecord"
    entity_id = models.IntegerField()
    summary = models.CharField(max_length=255, null=True, blank=True)
    before_data = models.JSONField(null=True, blank=True)
    after_data = models.JSONField(null=True, blank=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='dispatch_audit_logs')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} {self.entity_type} {self.entity_id} by {self.actor}"

    @property
    def diff_list(self):
        diffs = []
        before = self.before_data or {}
        after = self.after_data or {}
        if not isinstance(before, dict):
            before = {}
        if not isinstance(after, dict):
            after = {}

        DIFF_IGNORE_KEYS = {"created_at", "updated_at", "id", "pk", "deleted_at"}

        FIELD_LABELS = {
            "name": "Name",
            "email": "Email",
            "role": "Role",
            "phone": "Phone",
            "contact_number": "Contact #",
            "address": "Address",
            "barangay": "Barangay",
            "barangay_city": "Barangay / City",
            "client": "Client Name",
            "client_name": "Client Name",
            "account_no": "Account #",
            "concern": "Concern / Issue",
            "status": "Status",
            "status_option": "Status",
            "type_option": "Type",
            "chat_type_option": "Chat Type",
            "ticket_type": "Ticket Type",
            "priority": "Priority",
            "sales_agent": "Sales Agent",
            "technicians": "Assigned Techs",
            "teams": "Assigned Techs / Teams",
            "remarks": "Remarks",
            "actions_taken": "Actions Taken",
            "ticket_number": "Ticket #",
            "plan_package": "Plan Package",
            "cable_length": "Cable Length (m)",
            "signal_level": "Signal Level (dBm)",
            "signal_dbm": "Signal (dBm)",
            "nap_port": "NAP Port",
            "pole_number": "Pole #",
            "nap_reading": "NAP Reading (dBm)",
            "house_reading": "House Reading (dBm)",
            "ont_modem_sn": "ONT/Modem S/N",
            "ont_modem_mac": "ONT/Modem MAC",
            "onu_sn_mac": "ONU SN / MAC",
            "payment_method": "Payment Method",
            "payment_collected": "Payment Collected",
            "amount_paid": "Amount Paid",
            "receipt_no": "Receipt #",
            "facility": "Facility",
            "special_instruction": "Special Instruction",
            "technician_remarks": "Technician Remarks",
            "qa_notes": "QA Notes",
            "admin_notes": "Admin Notes",
            "time_start": "Service Start",
            "time_accomplish": "Service End",
            "done_at": "Date Completed",
            "color": "Color",
            "label": "Label",
            "active": "Active",
            "sort_order": "Sort Order",
        }

        all_keys = sorted(set(before.keys()).union(set(after.keys())))
        for k in all_keys:
            if k.lower() in DIFF_IGNORE_KEYS:
                continue
            old_v = before.get(k)
            new_v = after.get(k)
            if old_v != new_v:
                label = FIELD_LABELS.get(k, k.replace('_', ' ').title())
                diffs.append({
                    'field': k,
                    'label': label,
                    'old': str(old_v) if old_v is not None else '-',
                    'new': str(new_v) if new_v is not None else '-',
                    'is_change': (k in before and k in after),
                    'is_addition': (k not in before),
                    'is_deletion': (k not in after),
                })
        return diffs