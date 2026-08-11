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

class CustomerStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    SUSPENDED = 'suspended', 'Suspended'
    PENDING = 'pending', 'Pending'
    PULL_OUT = 'pull out', 'Pull Out'
    EXPIRED = 'expired', 'Expired'
    PAST_DUE = 'past_due', 'Past Due'

class Customer(models.Model):
    username = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    account_type = models.ForeignKey(AccountType, on_delete=models.SET_NULL, null=True, blank=True, related_name='customers')
    service_plan = models.ForeignKey(ServicePlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='customers')
    
    expires_at = models.DateTimeField(null=True, blank=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=CustomerStatus.choices, default=CustomerStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    adjusted_by_router = models.CharField(max_length=100, null=True, blank=True)
    adjusted_by_referral = models.CharField(max_length=250, null=True, blank=True)
    last_expiry_sms_sent = models.DateTimeField(null=True, blank=True)
    
    mikrotik_device = models.ForeignKey(MikrotikDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name='customers')
    
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    mac_address = models.CharField(max_length=32, null=True, blank=True)
    agent = models.CharField(max_length=100, null=True, blank=True)
    referral_received = models.CharField(max_length=250, null=True, blank=True)
    last_sms_due = models.DateTimeField(null=True, blank=True)
    
    # PPPoE Mikrotik Fields
    pppoe_password = models.CharField(max_length=128, null=True, blank=True)
    pppoe_profile = models.CharField(max_length=100, default='default', null=True, blank=True)

    connection = models.CharField(max_length=20)
    created_form_by = models.CharField(max_length=250)
    
    cignalplay_no = models.CharField(max_length=64, null=True, blank=True)
    cignalplay_date = models.DateField(null=True, blank=True)
    cignalplay_adjustedby = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.username or self.full_name
