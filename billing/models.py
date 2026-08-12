# pyrefly: ignore [missing-import]
from django.db import models
from network_manager.models import MikrotikDevice


class AccountType(models.Model):
    type_name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.type_name

class ServicePlan(models.Model):
    plan_code = models.CharField(max_length=64)
    plan_name = models.CharField(max_length=50)
    speed_up = models.IntegerField(null=True, blank=True)
    speed_down = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_30 = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    price_15 = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    price_3 = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    price_1 = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    validity_days = models.IntegerField()
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.plan_name

class Agent(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    password_hash = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=255) # Maps to plan_name
    speed_up = models.CharField(max_length=100) # e.g. "50 Mbps"
    speed_down = models.CharField(max_length=100) # e.g. "50 Mbps"
    price = models.DecimalField(max_digits=10, decimal_places=2)
    validity_days = models.IntegerField(default=30)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (₱{self.price})"

class SystemAdmin(models.Model):
    ROLE_CHOICES = (
        ('Admin', 'Admin'),
        ('Editor', 'Editor'),
        ('Viewer', 'Viewer'),
    )
    STATUS_CHOICES = (
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    )

    username = models.CharField(max_length=150, unique=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='Admin')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    password_hash = models.CharField(max_length=255) # We will hash this securely!
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name

class Barangay(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Customer(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
        ('pull out', 'Pull Out'),
    )

    # --- THE SUPERPOWER: Foreign Keys tying the system together ---
    plan = models.ForeignKey('SubscriptionPlan', on_delete=models.SET_NULL, null=True)
    agent = models.ForeignKey('Agent', on_delete=models.SET_NULL, null=True)
    barangay = models.ForeignKey('Barangay', on_delete=models.SET_NULL, null=True)
    account_type = models.ForeignKey('AccountType', on_delete=models.SET_NULL, null=True)
    mikrotik_device = models.ForeignKey(MikrotikDevice, on_delete=models.SET_NULL, null=True)

    # --- Core Details ---
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True) # We will store the 639... format
    address = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # --- Location (For the Map) ---
    latitude = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)

    # --- PPPoE Details ---
    pppoe_username = models.CharField(max_length=255, unique=True, null=True, blank=True)
    pppoe_password = models.CharField(max_length=255, null=True, blank=True)
    mac_address = models.CharField(max_length=100, null=True, blank=True)
    
    # --- Cignal Play Integration ---
    cignalplay_no = models.CharField(max_length=100, null=True, blank=True)
    cignalplay_date = models.DateTimeField(null=True, blank=True)

    # --- Audit Logs ---
    created_form_by = models.CharField(max_length=100, null=True, blank=True)
    adjusted_by_router = models.CharField(max_length=100, null=True, blank=True)
    cignalplay_adjustedby = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.pppoe_username})"

class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    username = models.CharField(max_length=255, null=True, blank=True)
    plan_name = models.CharField(max_length=100, null=True, blank=True)
    mikrotik_device_name = models.CharField(max_length=100, null=True, blank=True)
    
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
