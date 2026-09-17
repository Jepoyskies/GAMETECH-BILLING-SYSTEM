from django.db import models
from django.contrib.auth.models import User
from billing.models import Customer
from django.utils import timezone

class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Technician(models.Model):
    name = models.CharField(max_length=100, unique=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    target_per_day = models.IntegerField(default=0)
    target_per_month = models.IntegerField(default=0)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optionally link to the Django User if they log in
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name

class ConfigOption(models.Model):
    LIST_TYPE_CHOICES = (
        ('STATUS', 'STATUS'),
        ('TYPE', 'TYPE'),
        ('CHAT_TYPE', 'CHAT_TYPE'),
    )
    MODULE_CHOICES = (
        ('DISPATCH', 'DISPATCH'),
        ('MONITORING', 'MONITORING'),
    )
    list_type = models.CharField(max_length=20, choices=LIST_TYPE_CHOICES)
    module = models.CharField(max_length=20, choices=MODULE_CHOICES)
    label = models.CharField(max_length=100)
    color = models.CharField(max_length=50, default='gray')
    sort_order = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    hardcoded = models.BooleanField(default=False)
    
    dispatch_equivalent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='equivalent_of')

    class Meta:
        unique_together = ('list_type', 'module', 'label')

    def __str__(self):
        return f"{self.module} - {self.list_type}: {self.label}"

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
    sales_agent = models.CharField(max_length=100, null=True, blank=True)
    
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
    sales_agent = models.CharField(max_length=100, null=True, blank=True)
    
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
    dispatch = models.OneToOneField(DispatchRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='monitoring_record')
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
    entity_type = models.CharField(max_length=100) # e.g. "DispatchRecord", "MonitoringRecord"
    entity_id = models.IntegerField()
    summary = models.CharField(max_length=255, null=True, blank=True)
    before_data = models.JSONField(null=True, blank=True)
    after_data = models.JSONField(null=True, blank=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='dispatch_audit_logs')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} {self.entity_type} {self.entity_id} by {self.actor}"


class JobTicket(models.Model):
    TICKET_TYPE_CHOICES = (
        ('INSTALLATION', 'New Installation'),
        ('REPAIR', 'Repair / Client Concern'),
        ('CIGNAL', 'Cignal Play / Box'),
        ('MIGRATION', 'Plan / Line Migration'),
        ('RELOCATION', 'Relocation / Transfer'),
        ('PULL_OUT', 'Pull Out / Disconnection'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending Dispatch'),
        ('ASSIGNED', 'Assigned / Scheduled'),
        ('IN_PROGRESS', 'In Progress / On Site'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )
    PRIORITY_CHOICES = (
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    )
    SOURCE_TAB_CHOICES = (
        ('INTERNET_INSTALL', 'INTERNET_INSTALL'),
        ('CIGNAL_PLAY', 'CIGNAL_PLAY'),
        ('CLIENT_CONCERNS', 'CLIENT_CONCERNS'),
    )

    ticket_number = models.CharField(max_length=50, unique=True, blank=True)
    ticket_type = models.CharField(max_length=30, choices=TICKET_TYPE_CHOICES, default='INSTALLATION')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='NORMAL')
    source_tab = models.CharField(max_length=30, choices=SOURCE_TAB_CHOICES, default='INTERNET_INSTALL')

    # Smart CRM & Network Linkages
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='job_tickets')
    mikrotik_device = models.ForeignKey('network_manager.MikrotikDevice', on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatch_tickets')

    # Client / Applicant Snapshot
    client_name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    barangay = models.CharField(max_length=100, blank=True, null=True)
    contact_number = models.CharField(max_length=50, blank=True, null=True)
    alternate_contact = models.CharField(max_length=150, null=True, blank=True)
    facebook_account = models.CharField(max_length=255, null=True, blank=True)
    account_no = models.CharField(max_length=100, blank=True, null=True)
    sales_agent = models.CharField(max_length=100, blank=True, null=True)
    plan_package = models.CharField(max_length=100, blank=True, null=True)

    # Job / Concern Details
    concern = models.TextField(blank=True, null=True)
    chat_type = models.CharField(max_length=50, default='Walk-In / Direct', blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    special_instruction = models.TextField(blank=True, null=True)
    actions_taken = models.TextField(blank=True, null=True)

    # Assignment & Scheduling
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='job_tickets')
    technicians = models.ManyToManyField(Technician, blank=True, related_name='job_tickets')
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.CharField(max_length=100, null=True, blank=True)

    # GPS Coordinates
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Technical Specs & Hardware Completion (100% extracted from legacy JobDetail)
    nap_port = models.CharField(max_length=100, null=True, blank=True)
    cable_length = models.CharField(max_length=100, null=True, blank=True)
    nap_reading = models.CharField(max_length=100, null=True, blank=True)
    pole_number = models.CharField(max_length=100, null=True, blank=True)
    ont_modem_sn = models.CharField(max_length=100, null=True, blank=True)
    signal_level = models.CharField(max_length=100, null=True, blank=True)
    facility = models.CharField(max_length=100, null=True, blank=True)
    house_reading = models.CharField(max_length=100, null=True, blank=True)
    technician_remarks = models.TextField(null=True, blank=True)
    acknowledged_by = models.CharField(max_length=100, null=True, blank=True)

    # Timers & SLA
    time_start = models.DateTimeField(null=True, blank=True)
    time_accomplish = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True, help_text="Duration in minutes")
    done_at = models.DateTimeField(null=True, blank=True)
    done_duration = models.IntegerField(null=True, blank=True)
    sla_rebates_given = models.IntegerField(default=0)
    
    # New Fields for QA and Payment
    payment_collected = models.CharField(max_length=50, blank=True, null=True)
    qa_notes = models.TextField(blank=True, null=True)
    qa_completed_at = models.DateTimeField(null=True, blank=True)

    # Audit & Dispatcher Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatched_tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            date_prefix = timezone.now().strftime("%Y%m%d")
            today_count = JobTicket.objects.filter(created_at__date=timezone.now().date()).count() + 1
            self.ticket_number = f"TICK-{date_prefix}-{today_count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_number} - {self.client_name} ({self.get_status_display()})"
