# pyrefly: ignore [missing-import]
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.models import User
from network_manager.models import MikrotikDevice


class AccountType(models.Model):
    type_name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.type_name



class Agent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='agent_profile')
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    password_hash = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=255)  # Maps to plan_name
    speed_up = models.CharField(max_length=100)  # e.g. "50 Mbps"
    speed_down = models.CharField(max_length=100)  # e.g. "50 Mbps"
    price = models.DecimalField(max_digits=10, decimal_places=2)
    validity_days = models.IntegerField(default=30)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_name = self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._original_name = self.name

    def __str__(self):
        return f"{self.name} (₱{self.price})"

    class Meta:
        ordering = ['price']


class SystemAdmin(models.Model):
    ROLE_CHOICES = (
        ('Admin', 'Admin'),
        ('Technician', 'Technician'),
        ('Agent', 'Agent'),
        ('CSR', 'CSR'),
    )
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    )

    username = models.CharField(max_length=150, unique=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=50, choices=ROLE_CHOICES, default='Admin')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='Active')
    password_hash = models.CharField(
        max_length=255)  # We will hash this securely!
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Barangay(models.Model):
    name = models.CharField(max_length=100)
    health_status = models.CharField(max_length=20, choices=[('Excellent', 'Excellent'), ('Moderate', 'Moderate'), ('Poor', 'Poor'), ('Outage', 'Outage')], default='Excellent')
    health_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


import random
import string

def generate_portal_password(length=8):
    """Generate a random alphanumeric password."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

class Customer(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
        ('pull out', 'Pull Out'),
    )

    SYNC_CHOICES = (
        ('Synced', 'Synced'),
        ('Failed', 'Failed'),
    )
    sync_status = models.CharField(max_length=20, choices=SYNC_CHOICES, default='Synced')

    # --- THE SUPERPOWER: Foreign Keys tying the system together ---
    plan = models.ForeignKey(
        'SubscriptionPlan', on_delete=models.SET_NULL, null=True)
    agent = models.ForeignKey('Agent', on_delete=models.SET_NULL, null=True)
    barangay = models.ForeignKey(
        'Barangay', on_delete=models.SET_NULL, null=True)
    account_type = models.ForeignKey(
        'AccountType', on_delete=models.SET_NULL, null=True)
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    mikrotik_device = models.ForeignKey(
        MikrotikDevice, on_delete=models.SET_NULL, null=True)

    # --- Core Details ---
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, null=True, blank=True)
    # We will store the 639... format
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active')
    portal_password = models.CharField(max_length=50, blank=True, null=True)
    must_change_password = models.BooleanField(default=True)
    CONNECTION_STATUS_CHOICES = (
        ('Offline', 'Offline'),
        ('Low', 'Low'),
        ('Poor', 'Poor'),
        ('Unstable', 'Unstable'),
        ('Stable', 'Stable'),
        ('Good', 'Good'),
        ('Strong', 'Strong'),
        ('Excellent', 'Excellent'), # Keep for backwards compatibility
        ('Outage', 'Outage'),
    )
    health_status = models.CharField(max_length=20, choices=CONNECTION_STATUS_CHOICES, default='Good')
    health_reason = models.TextField(blank=True, null=True, help_text="Message for the customer regarding their connection status.")

    # --- Location (For the Map) ---
    latitude = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True)

    # --- PPPoE Details ---
    pppoe_username = models.CharField(
        max_length=255, unique=True, null=True, blank=True)
    pppoe_password = models.CharField(max_length=255, null=True, blank=True)
    mac_address = models.CharField(max_length=100, null=True, blank=True)

    # --- Cignal Play Integration ---
    cignalplay_no = models.CharField(max_length=100, null=True, blank=True)
    cignalplay_date = models.DateTimeField(null=True, blank=True)

    # --- Audit Logs ---
    created_form_by = models.CharField(max_length=100, null=True, blank=True)
    adjusted_by_router = models.CharField(
        max_length=100, null=True, blank=True)
    cignalplay_adjustedby = models.CharField(
        max_length=100, null=True, blank=True)
    referral_received = models.CharField(max_length=50, null=True, blank=True, default='0')
    adjusted_by_referral = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def get_status_display_badge(self):
        return f'<span class="badge badge-{self.status}">{self.get_status_display()}</span>'

    def save(self, *args, **kwargs):
        if not self.portal_password:
            self.portal_password = generate_portal_password()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.pppoe_username})"

    @property
    def abs_outstanding_balance(self):
        return abs(self.outstanding_balance) if self.outstanding_balance else 0

    @property
    def advance_months_covered(self):
        if self.outstanding_balance < 0 and self.plan and self.plan.price > 0:
            return int(abs(self.outstanding_balance) // self.plan.price)
        return 0

    @property
    def is_suspicious(self):
        import re
        if not self.pppoe_username:
            return False
            
        # Check for weird characters in username
        if re.search(r'[^a-zA-Z0-9\.\-\_]', self.pppoe_username):
            return True
            
        # Check if plan is missing or suspiciously named 'default'
        if not self.plan or self.plan.name.lower() == 'default':
            return True
            
        # Check if barangay is missing
        if not self.barangay:
            return True
            
        return False



class Payment(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    username = models.CharField(max_length=255, null=True, blank=True)
    plan_name = models.CharField(max_length=100, null=True, blank=True)
    mikrotik_device_name = models.CharField(
        max_length=100, null=True, blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    days_paid = models.FloatField(null=True, blank=True)
    payment_method = models.CharField(max_length=50)
    reference_no = models.CharField(max_length=100, null=True, blank=True)
    reason = models.CharField(max_length=255, null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    payment_date_received = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    adjusted_by = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment by {self.username} - ₱{self.amount}"

class SystemLog(models.Model):
    table_name = models.CharField(max_length=255)
    record_id = models.CharField(max_length=255)
    action = models.CharField(max_length=50) # ADD, UPDATE, DELETE
    changed_by = models.CharField(max_length=255)
    target_name = models.CharField(max_length=255, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    old_data = models.TextField(null=True, blank=True)
    new_data = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-changed_at']
        db_table = 'system_logs'

    def __str__(self):
        return f"{self.action} on {self.table_name} by {self.changed_by} at {self.changed_at}"

class CustomerMacHistory(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='mac_history')
    mac_address = models.CharField(max_length=100)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-detected_at']
        db_table = 'customer_mac_history'

    def __str__(self):
        return f"{self.mac_address} for {self.customer.full_name}"

class Rebate(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, related_name='rebates')
    username = models.CharField(max_length=255, null=True, blank=True)
    plan_name = models.CharField(max_length=255, null=True, blank=True)
    days = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    current_expiry = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    adjusted_by = models.CharField(max_length=255, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rebate for {self.username}"
class SmsLog(models.Model):
    phone = models.CharField(max_length=20)
    message = models.TextField()
    response = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='success')
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sms_log'
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.phone} - {self.status}"


class CignalPlay(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='cignal_plans')
    plan_name = models.CharField(max_length=255)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    adjusted_by = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cignal_play'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.plan_name} for {self.customer.full_name}"

class AuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    admin_user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='audit_logs')
    action_type = models.CharField(max_length=100)
    remarks = models.TextField()

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action_type} on {self.customer.full_name} at {self.timestamp}"


class EmployeeProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    branch_location = models.CharField(max_length=255, blank=True, null=True)
    employee_id = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} Profile"

class JobOrder(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )
    TYPE_CHOICES = (
        ('Installation', 'Installation'),
        ('Repair', 'Repair'),
        ('Replacement', 'Replacement'),
        ('Relocation', 'Relocation'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='job_orders')
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'groups__name': 'Technician'})
    job_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    
    reported_issue = models.TextField(help_text="What the CSR/Agent reported")
    resolution_notes = models.TextField(blank=True, null=True, help_text="What the Technician did")
    
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_job_orders')

    def __str__(self):
        return f"{self.job_type} - {self.customer.full_name} ({self.status})"

class AddOnRequest(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addon_requests')
    addon_type = models.CharField(max_length=100) # e.g. 'Cignal Play Add-on', 'Cignal Box'
    status = models.CharField(max_length=20, default='Pending') # 'Pending', 'Resolved'
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.full_name} - {self.addon_type} ({self.status})"

    class Meta:
        ordering = ['-requested_at']


class Notification(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50) # 'payment', 'network', 'cignal', 'system'
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title}"


class ImprovementRequest(models.Model):
    STATUS_CHOICES = (
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    )
    submitted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField(help_text="What does Sir Romnick want improved?")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    dev_note = models.TextField(blank=True, null=True, help_text="Developer's response or note")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Request by {self.submitted_by} on {self.created_at.strftime('%Y-%m-%d')}"


@receiver(post_save, sender=User)
def sync_superuser_to_systemadmin(sender, instance, created, **kwargs):
    """
    Automatically creates or updates a SystemAdmin record whenever a superuser is created or saved.
    This ensures `createsuperuser` immediately shows up in the Staff & Admins list.
    """
    if instance.is_superuser:
        sys_admin, was_created = SystemAdmin.objects.get_or_create(
            username=instance.username,
            defaults={
                'full_name': f"{instance.first_name} {instance.last_name}".strip() or instance.username,
                'email': instance.email or f"{instance.username}@example.com",
                'role': 'Admin',
                'status': 'Active' if instance.is_active else 'Inactive',
                'password_hash': 'managed_by_django'
            }
        )
        if not was_created:
            updated = False
            if sys_admin.role != 'Admin':
                sys_admin.role = 'Admin'
                updated = True
            if sys_admin.status != ('Active' if instance.is_active else 'Inactive'):
                sys_admin.status = 'Active' if instance.is_active else 'Inactive'
                updated = True
            if updated:
                sys_admin.save(update_fields=['role', 'status'])

