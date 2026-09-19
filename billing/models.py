# pyrefly: ignore [missing-import]
from decimal import Decimal
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
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agent_profile",
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    password_hash = models.CharField(max_length=255, blank=True, null=True)
    is_test_data = models.BooleanField(
        default=False, help_text="Flags test agents to safely ignore without hard-deleting"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def claimable_commission(self):
        """
        Total claimable commission from CommissionTransactions.
        """
        from django.db.models import Sum
        total = self.commissiontransaction_set.filter(status='CLAIMABLE').aggregate(total=Sum('amount'))['total']
        return total or 0

    @property
    def qualified_customers_count(self):
        """Count of referred customers who have qualified with >= 2 payments."""
        from django.db.models import Count
        return self.customer_set.annotate(pay_count=Count('payments')).filter(pay_count__gte=2).count()

    @property
    def is_cashout_eligible(self):
        """Gated behind 5 qualifying customers and ₱2,500 claimable commission."""
        return self.qualified_customers_count >= 5 and self.claimable_commission >= 2500

    def __str__(self):
        return self.name


class CommissionTransaction(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CLAIMABLE', 'Claimable'),
        ('PAID', 'Paid'),
        ('REVERSED', 'Reversed'),
    )
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)
    customer = models.ForeignKey("Customer", on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    is_test_data = models.BooleanField(default=False, help_text="Flags historical/test records to exclude from financial reports")

    class Meta:
        unique_together = ('agent', 'customer')

    def __str__(self):
        return f"{self.agent.name} - {self.amount} ({self.status})"


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
        ordering = ["price"]


class AddonPlan(models.Model):
    ADDON_TYPE_CHOICES = (
        ("Cignal Play", "Cignal Play"),
        ("Cignal Box", "Cignal Box"),
        ("Other", "Other"),
    )

    name = models.CharField(max_length=150)
    addon_type = models.CharField(
        max_length=50, choices=ADDON_TYPE_CHOICES, default="Cignal Play"
    )
    duration_days = models.IntegerField(default=30)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.addon_type}) - ₱{self.price}"

    class Meta:
        ordering = ["price"]
        verbose_name = "Add-on Plan"
        verbose_name_plural = "Add-on Plans"


class StaffRole(models.Model):
    name = models.CharField(max_length=50, unique=True)
    can_access_billing = models.BooleanField(default=False)
    can_access_network_ops = models.BooleanField(default=False)
    can_access_cignal_play = models.BooleanField(default=False)
    can_access_dispatch = models.BooleanField(default=False)
    can_access_administration = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class SystemAdmin(models.Model):
    STATUS_CHOICES = (
        ("Active", "Active"),
        ("Inactive", "Inactive"),
    )

    username = models.CharField(max_length=150, unique=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=50, default="Agent")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    password_hash = models.CharField(max_length=255)  # We will hash this securely!
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Barangay(models.Model):
    name = models.CharField(max_length=100)
    health_status = models.CharField(
        max_length=20,
        choices=[
            ("Excellent", "Excellent"),
            ("Moderate", "Moderate"),
            ("Poor", "Poor"),
            ("Outage", "Outage"),
        ],
        default="Excellent",
    )
    health_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


import random
import string


def generate_portal_password(length=8):
    """Generate a random alphanumeric password."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


class Customer(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("expired", "Expired"),
        ("inactive", "Inactive"),
        ("pending", "Pending"),
        ("suspended", "Suspended"),
        ("pull out", "Pull Out"),
    )

    SYNC_CHOICES = (
        ("Synced", "Synced"),
        ("Failed", "Failed"),
    )
    sync_status = models.CharField(
        max_length=20, choices=SYNC_CHOICES, default="Synced"
    )

    # --- THE SUPERPOWER: Foreign Keys tying the system together ---
    plan = models.ForeignKey("SubscriptionPlan", on_delete=models.SET_NULL, null=True)
    agent = models.ForeignKey("Agent", on_delete=models.SET_NULL, null=True)
    agent_lock_until = models.DateTimeField(null=True, blank=True, help_text="Calculated 60 days from Stage 5 Admin Approval. Until this date, the customer cannot use staggered payments.")
    barangay = models.ForeignKey("Barangay", on_delete=models.SET_NULL, null=True)
    account_type = models.ForeignKey(
        "AccountType", on_delete=models.SET_NULL, null=True
    )
    outstanding_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    mikrotik_device = models.ForeignKey(
        MikrotikDevice, on_delete=models.SET_NULL, null=True
    )

    # --- Core Details ---
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, null=True, blank=True)
    # We will store the 639... format
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active", db_index=True
    )
    portal_password = models.CharField(max_length=50, blank=True, null=True)
    must_change_password = models.BooleanField(default=True)

    # Audit & Testing
    is_test_data = models.BooleanField(default=False, help_text="Flags test accounts to safely ignore without hard-deleting")

    CONNECTION_STATUS_CHOICES = (
        ("Offline", "Offline"),
        ("Low", "Low"),
        ("Poor", "Poor"),
        ("Unstable", "Unstable"),
        ("Stable", "Stable"),
        ("Good", "Good"),
        ("Strong", "Strong"),
        ("Excellent", "Excellent"),  # Keep for backwards compatibility
        ("Outage", "Outage"),
    )
    health_status = models.CharField(
        max_length=20, choices=CONNECTION_STATUS_CHOICES, default="Good"
    )
    health_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Message for the customer regarding their connection status.",
    )

    # --- Location (For the Map) ---
    latitude = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True
    )

    # --- PPPoE Details ---
    pppoe_username = models.CharField(
        max_length=255, unique=True, null=True, blank=True
    )
    pppoe_password = models.CharField(max_length=255, null=True, blank=True)
    mac_address = models.CharField(max_length=100, null=True, blank=True)

    # --- Cignal Play & Box Integration ---
    cignalplay_no = models.CharField(max_length=100, null=True, blank=True)
    cignalplay_date = models.DateTimeField(null=True, blank=True)
    cignalbox_no = models.CharField(max_length=100, null=True, blank=True)
    cignalbox_date = models.DateTimeField(null=True, blank=True)

    # --- Security & Verification ---
    is_verified = models.BooleanField(default=False)

    # --- Prospect Application & Identity ---
    preferred_installation_date = models.DateField(null=True, blank=True, help_text="Requested date for initial installation")
    id_type = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. UMID, PhilSys, Driver's License, Passport")
    id_number = models.CharField(max_length=100, blank=True, null=True, help_text="ID card serial or identification number")
    PAYMENT_METHOD_CHOICES = (
        ("cash", "Cash on Hand"),
        ("gcash", "Direct GCash"),
    )
    preferred_payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash", help_text="Payment method chosen during prospect application"
    )

    @property
    def masked_id_number(self):
        """Returns 32•••••23 masked representation of government ID."""
        if not self.id_number:
            return ""
        s = str(self.id_number).strip()
        if len(s) <= 4:
            return "•" * len(s)
        return f"{s[:2]}{'•' * (len(s) - 4)}{s[-2:]}"

    @property
    def staleness_hours(self):
        if not self.created_at:
            return 0
        from django.utils import timezone
        delta = timezone.now() - self.created_at
        return int(delta.total_seconds() // 3600)

    @property
    def sla_badge_level(self):
        h = self.staleness_hours
        if h >= 48:
            return 'red'
        elif h >= 24:
            return 'amber'
        return 'normal'

    # --- Audit Logs ---
    created_form_by = models.CharField(max_length=100, null=True, blank=True)
    adjusted_by_router = models.CharField(max_length=100, null=True, blank=True)
    cignalplay_adjustedby = models.CharField(max_length=100, null=True, blank=True)
    cignalbox_adjustedby = models.CharField(max_length=100, null=True, blank=True)
    referral_received = models.CharField(
        max_length=50, null=True, blank=True, default="0"
    )
    adjusted_by_referral = models.CharField(max_length=100, null=True, blank=True)
    INSTALLATION_STATUS_CHOICES = (
        ("installed", "Installed"),
        ("pending", "Pending Installation"),
    )
    installation_status = models.CharField(
        max_length=20,
        choices=INSTALLATION_STATUS_CHOICES,
        default="installed",
        db_index=True,
        help_text="Physical installation status of the subscriber line.",
    )
    installed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when physical installation was completed.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def get_status_display_badge(self):
        return f'<span class="badge badge-{self.status}">{self.get_status_display()}</span>'

    def save(self, *args, **kwargs):
        if not self.portal_password:
            self.portal_password = generate_portal_password()
        if self.status == "suspended" and not getattr(self, "_preserve_expiration", False):
            self.expires_at = None
            if "update_fields" in kwargs and kwargs["update_fields"] is not None:
                fields = set(kwargs["update_fields"])
                fields.add("expires_at")
                kwargs["update_fields"] = list(fields)
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
    def suspicious_reasons(self):
        import re

        reasons = []

        if self.pppoe_username and re.search(
            r"[^a-zA-Z0-9\.\-\_]", self.pppoe_username
        ):
            reasons.append("Username contains invalid or suspicious characters")

        if not self.plan or self.plan.name.lower() == "default":
            reasons.append("Using an unauthorized 'default' or missing plan")

        if not self.barangay:
            reasons.append("Missing Barangay assignment")

        return reasons

    @property
    def username(self):
        return self.pppoe_username

    @property
    def is_suspicious(self):
        return len(self.suspicious_reasons) > 0

    @property
    def is_walkin_or_direct(self):
        if not self.agent:
            return True
        agent_name = (self.agent.name or "").lower()
        return "walk-in" in agent_name or "direct" in agent_name

    @property
    def can_pay_staggered(self):
        now = timezone.now()
        
        # New Explicit Lock Logic
        if self.agent_lock_until and now < self.agent_lock_until:
            return False
            
        start_date = self.installed_at or self.created_at or now
        days_active = (now - start_date).days
        payments_count = self.payments.count() if self.pk else 0

        if self.is_walkin_or_direct:
            # Walk-in / Direct: unlocked after first payment or after first month (>= 30 days)
            return payments_count >= 1 or days_active >= 30
        else:
            # Has an Agent: only unlocked after 3 months (>= 90 days) or after 3 payments
            return payments_count >= 3 or days_active >= 90

    @property
    def staggered_restriction_reason(self):
        if self.can_pay_staggered:
            return None
            
        if self.agent_lock_until and timezone.now() < self.agent_lock_until:
            return f"Staggered payments are locked until {self.agent_lock_until.strftime('%b %d, %Y')}."
            
        if self.is_walkin_or_direct:
            return "Please complete your initial full monthly payment to unlock staggered payments."
        else:
            now = timezone.now()
            start_date = self.installed_at or self.created_at or now
            days_active = (now - start_date).days
            days_left = max(1, 90 - days_active)
            months_left = max(1, (days_left + 29) // 30)
            return f"Staggered payments unlock after your first 3 months of service (~{months_left} mo remaining)."

    def generate_mikrotik_comment(self):
        latest_payment = self.payments.order_by("-created_at").first()

        comment_parts = []
        if latest_payment:
            paid_str = latest_payment.created_at.strftime("%b %d, %Y")
            expiry_str = (
                self.expires_at.strftime("%b %d, %Y") if self.expires_at else "None"
            )
            plan_name = self.plan.name if self.plan else "No Plan"
            payment_method = latest_payment.payment_method
            admin_name = (
                latest_payment.adjusted_by if latest_payment.adjusted_by else "Admin"
            )
            reason = latest_payment.reason if latest_payment.reason else ""

            pay_comment = f"paid {paid_str} exp {expiry_str} . {plan_name} . {payment_method} . {admin_name}"
            if reason:
                pay_comment += f" . {reason}"
            comment_parts.append(pay_comment)

        # Add Profile Details
        profile_parts = [str(self.full_name) if self.full_name else "Unknown"]

        if self.phone:
            profile_parts.append(str(self.phone))

        if not latest_payment and self.expires_at:
            profile_parts.append(f"Exp: {self.expires_at.strftime('%Y-%m-%d')}")

        comment_parts.append(" | ".join(profile_parts))
        secret_comment = " || ".join(comment_parts)

        # Final cleanup for Mikrotik comment compatibility (remove non-printable chars)
        secret_comment = "".join(c for c in secret_comment if c.isprintable())
        return secret_comment


class Payment(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    username = models.CharField(max_length=255, null=True, blank=True)
    plan_name = models.CharField(max_length=100, null=True, blank=True)
    mikrotik_device_name = models.CharField(max_length=100, null=True, blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    days_paid = models.FloatField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, db_index=True)
    reference_no = models.CharField(max_length=100, null=True, blank=True)
    reason = models.CharField(max_length=255, null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    payment_date_received = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    adjusted_by = models.CharField(max_length=100, null=True, blank=True)

    # Audit & Testing
    is_test_data = models.BooleanField(default=False, help_text="Flags test payments to exclude from revenue")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"Payment by {self.username} - ₱{self.amount}"


class SystemLog(models.Model):
    table_name = models.CharField(max_length=255)
    record_id = models.CharField(max_length=255)
    action = models.CharField(max_length=50)  # ADD, UPDATE, DELETE
    changed_by = models.CharField(max_length=255)
    target_name = models.CharField(max_length=255, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    old_data = models.TextField(null=True, blank=True)
    new_data = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-changed_at"]
        db_table = "system_logs"

    def __str__(self):
        return f"{self.action} on {self.table_name} by {self.changed_by} at {self.changed_at}"

    @property
    def specific_action(self):
        act_raw = (self.action or "").strip()
        act_upper = act_raw.upper()

        if "BALANCE_RESET" in act_upper or "RESET_BALANCE" in act_upper:
            return "Balance Reset"
        if "LOGIN" in act_upper:
            return "User Login"
        if "LOGOUT" in act_upper:
            return "User Logout"
        if "PASSWORD_CHANGE" in act_upper:
            return "Password Change"
        if "FORCE_SUSPEND" in act_upper:
            return "Force Suspend"
        if "FORCE_REACTIVATE" in act_upper:
            return "Force Reactivate"
        if "VERIFY" in act_upper:
            return "Unverify Account" if "UNVERIFY" in act_upper else "Verify Account"

        tbl = (self.table_name or "").lower()
        if act_upper in ["ADD", "CREATE", "INSERT"]:
            if "customer" in tbl:
                return "New Customer"
            elif "payment" in tbl:
                return "New Payment"
            elif "plan" in tbl:
                return "New Plan"
            elif "barangay" in tbl:
                return "New Barangay"
            elif "account" in tbl:
                return "New Account Type"
            elif "router" in tbl or "mikrotik" in tbl:
                return "New Router"
            return f"New {self.table_name}"

        if act_upper in ["DELETE", "REMOVE"]:
            if "customer" in tbl:
                return "Delete Customer"
            elif "payment" in tbl:
                return "Void Payment"
            elif "plan" in tbl:
                return "Delete Plan"
            return f"Delete {self.table_name}"

        # If it's already a specific custom action (not a generic UPDATE), return title-cased
        if act_upper not in ["UPDATE", "UPDATE (PROFILE)", "CHANGE", "EDIT"]:
            return act_raw.replace("_", " ").title()

        # For generic UPDATE actions, derive specific field(s) from old_data and new_data
        old = (self.old_data or "").lower()
        new = (self.new_data or "").lower()
        comb = old + "\n" + new

        categories = []
        if any(k in comb for k in ["latitude", "longitude"]):
            categories.append("Location")
        if "agent" in comb:
            categories.append("Agent")
        if any(k in comb for k in ["address", "barangay"]):
            categories.append("Address")
        if "plan" in comb:
            categories.append("Plan")
        if "status" in comb:
            categories.append("Status")
        if "expiration" in comb:
            categories.append("Expiration")
        if "balance" in comb:
            categories.append("Balance")
        if any(k in comb for k in ["phone", "email"]):
            categories.append("Contact")
        if any(k in comb for k in ["password", "username", "pppoe"]):
            categories.append("Credentials")
        if any(k in comb for k in ["router", "mikrotik"]):
            categories.append("Router")
        if any(k in comb for k in ["account_type", "account type"]):
            categories.append("Account Type")
        if "cignal" in comb:
            categories.append("Cignal Play")
        if any(k in comb for k in ["health_status", "health reason", "health"]):
            categories.append("Health Status")
        if any(k in comb for k in ["verified", "is_verified"]):
            categories.append("Verification")
        if any(k in comb for k in ["full_name", "name:"]):
            categories.append("Name")

        cats = list(dict.fromkeys(categories))
        if len(cats) == 1:
            if cats[0] == "Balance":
                return "Balance Override"
            if cats[0] == "Verification":
                return "Account Verified"
            return f"Change {cats[0]}"
        elif len(cats) == 2:
            return f"Change {cats[0]} & {cats[1]}"
        elif len(cats) > 2:
            return "Profile Update"

        return "Profile Update" if "customer" in tbl else f"Update {self.table_name}"


class CustomerMacHistory(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="mac_history"
    )
    mac_address = models.CharField(max_length=100)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-detected_at"]
        db_table = "customer_mac_history"

    def __str__(self):
        return f"{self.mac_address} for {self.customer.full_name}"


class Rebate(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, related_name="rebates"
    )
    username = models.CharField(max_length=255, null=True, blank=True)
    plan_name = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    days = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    current_expiry = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(default=timezone.now)
    adjusted_by = models.CharField(max_length=255, null=True, blank=True)

    # Audit & Testing
    is_test_data = models.BooleanField(default=False, help_text="Flags test payments to exclude from revenue")

    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rebate for {self.username}"


class SmsLog(models.Model):
    phone = models.CharField(max_length=20)
    message = models.TextField()
    response = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default="success")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sms_log"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.phone} - {self.status}"


class CignalPlay(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="cignal_plans"
    )
    plan_name = models.CharField(max_length=255)
    cignal_play_no = models.CharField(max_length=100, null=True, blank=True)
    cignal_box_no = models.CharField(max_length=100, null=True, blank=True)
    account_name = models.CharField(max_length=150, null=True, blank=True, help_text="e.g. Living Room TV")
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    adjusted_by = models.CharField(max_length=100, null=True, blank=True)
    hardware_payment_type = models.CharField(
        max_length=30,
        choices=[
            ("cashout", "Cashout ₱3k"),
            ("installment", "Installment ₱250/mo"),
            ("none", "App Only / No Box"),
        ],
        default="none",
    )
    installments_paid = models.IntegerField(default=0)
    monthly_load_plan = models.CharField(
        max_length=20,
        choices=[
            ("149", "42 Channels (₱149)"),
            ("399", "62 Channels (₱399)"),
        ],
        default="149",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_cancelled = models.BooleanField(default=False, db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "cignal_play"
        ordering = ["-created_at"]

    @property
    def label(self):
        return self.account_name or self.plan_name or "Cignal Subscription"

    @property
    def addon_type(self):
        return "Cignal Subscription"

    @property
    def account_number(self):
        return self.cignal_play_no or self.cignal_box_no or ""

    @property
    def cignal_account_number(self):
        return self.cignal_play_no or self.cignal_box_no or ""

    @property
    def is_active(self):
        if self.is_cancelled:
            return False
        exp = self.expiration_date or self.end_date
        if not exp:
            return False
        from django.utils import timezone
        now = timezone.now()
        # Normalise: exp may be a datetime or date
        if hasattr(exp, 'hour'):
            if timezone.is_naive(exp):
                exp = timezone.make_aware(exp, timezone.get_current_timezone())
            return exp >= now
        from datetime import date
        if isinstance(exp, date):
            return exp >= timezone.localdate()
        return False

    @property
    def is_hardware_fully_paid(self):
        if self.hardware_payment_type == 'cashout':
            return True
        if self.hardware_payment_type == 'installment':
            return (self.installments_paid or 0) >= 12
        return True

    @property
    def is_installment_ongoing(self):
        return self.hardware_payment_type == 'installment' and (self.installments_paid or 0) < 12

    @property
    def hardware_total_amount(self):
        if self.hardware_payment_type in ('cashout', 'installment'):
            return 3000
        return 0

    @property
    def hardware_paid_amount(self):
        if self.hardware_payment_type == 'cashout':
            return 3000
        elif self.hardware_payment_type == 'installment':
            months = min(max(self.installments_paid or 0, 0), 12)
            return months * 250
        return 0

    @property
    def hardware_remaining_amount(self):
        if self.hardware_payment_type == 'cashout':
            return 0
        elif self.hardware_payment_type == 'installment':
            paid = self.hardware_paid_amount
            return max(3000 - paid, 0)
        return 0

    @property
    def hardware_remaining_months(self):
        if self.hardware_payment_type == 'installment':
            months = min(max(self.installments_paid or 0, 0), 12)
            return max(12 - months, 0)
        return 0

    @property
    def hardware_paid_formatted(self):
        return f"{self.hardware_paid_amount:,}"

    @property
    def hardware_remaining_formatted(self):
        return f"{self.hardware_remaining_amount:,}"

    @property
    def is_installment_completed(self):
        return self.hardware_payment_type == 'installment' and (self.installments_paid or 0) >= 12

    @property
    def load_plan_display(self):
        if self.monthly_load_plan == '149':
            return "42 Channels (₱149/mo)"
        elif self.monthly_load_plan == '399':
            return "62 Channels (₱399/mo)"
        elif self.monthly_load_plan:
            return f"₱{self.monthly_load_plan}/mo"
        return "No Load Set"

    @property
    def days_until_expiry(self):
        """Returns days remaining until expiration (int), or None if no date. Can be negative if expired."""
        exp = self.expiration_date or self.end_date
        if not exp:
            return None
        from django.utils import timezone
        from datetime import date
        today = timezone.localdate()
        exp_date = exp.date() if hasattr(exp, 'date') else exp
        return (exp_date - today).days

    @property
    def is_box(self):
        t = f"{self.addon_type or ''} {self.plan_name or ''}".lower()
        return "box" in t

    @property
    def is_tv_box_completed(self):
        if not self.is_box:
            return False
        return (self.amount_paid or Decimal("0.00")) >= Decimal("3000.00")

    @property
    def tv_box_progress(self):
        paid = self.amount_paid or Decimal("0.00")
        target = Decimal("3000.00")
        months_paid = min(12, int(paid // Decimal("250.00")))
        remaining = max(Decimal("0.00"), target - paid)
        pct = min(100, int((paid / target) * 100)) if target > 0 else 100
        return {
            "paid": paid,
            "target": target,
            "remaining": remaining,
            "months_paid": months_paid,
            "total_months": 12,
            "pct": pct,
            "is_completed": paid >= target,
        }

    @property
    def channel_display_badge(self):
        if self.is_box:
            if self.is_tv_box_completed:
                return "TV Box (Completed - ₱3,000)"
            return f"TV Box ({self.tv_box_progress['months_paid']}/12 Mos)"
        paid = self.amount_paid or Decimal("0.00")
        name = self.plan_name or ""
        if paid == Decimal("149.00") or "149" in name or "42" in name:
            return "42 Channels (₱149/mo)"
        if paid == Decimal("399.00") or "399" in name or "62" in name:
            return "62 Channels (₱399/mo)"
        return self.plan_name or "Cignal Play"

    def save(self, *args, **kwargs):
        if self.expiration_date and not self.end_date:
            self.end_date = self.expiration_date
        elif self.end_date and not self.expiration_date:
            self.expiration_date = self.end_date
        super().save(*args, **kwargs)

    def __str__(self):
        lbl = f" ({self.account_name})" if self.account_name else ""
        nums = []
        if self.cignal_play_no:
            nums.append(f"Play: {self.cignal_play_no}")
        if self.cignal_box_no:
            nums.append(f"Box: {self.cignal_box_no}")
        num_str = " | ".join(nums) if nums else "No Numbers"
        return f"{self.plan_name}{lbl} - {num_str} for {self.customer.full_name}"


class AuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    admin_user = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="audit_logs"
    )
    action_type = models.CharField(max_length=100)
    remarks = models.TextField()

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action_type} on {self.customer.full_name} at {self.timestamp}"


class EmployeeProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="employee_profile"
    )
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    branch_location = models.CharField(max_length=255, blank=True, null=True)
    employee_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} Profile"


class JobOrder(models.Model):
    STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    )
    TYPE_CHOICES = (
        ("Installation", "Installation"),
        ("Repair", "Repair"),
        ("Replacement", "Replacement"),
        ("Relocation", "Relocation"),
    )

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="job_orders"
    )
    technician = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"groups__name": "Technician"},
    )
    job_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Pending")

    reported_issue = models.TextField(help_text="What the CSR/Agent reported")
    resolution_notes = models.TextField(
        blank=True, null=True, help_text="What the Technician did"
    )

    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_job_orders"
    )

    def __str__(self):
        return f"{self.job_type} - {self.customer.full_name} ({self.status})"


class AddOnRequest(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="addon_requests"
    )
    addon_type = models.CharField(
        max_length=100
    )  # e.g. 'Cignal Play Add-on', 'Cignal Box'
    status = models.CharField(max_length=20, default="Pending")  # 'Pending', 'Resolved'
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.full_name} - {self.addon_type} ({self.status})"

    class Meta:
        ordering = ["-requested_at"]


class Notification(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=50
    )  # 'payment', 'network', 'cignal', 'system'
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.notification_type}] {self.title}"


class ImprovementRequest(models.Model):
    STATUS_CHOICES = (
        ("new", "New"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    )
    submitted_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    message = models.TextField(help_text="What does Sir Romnick want improved?")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)
    dev_note = models.TextField(
        blank=True, null=True, help_text="Developer's response or note"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Request by {self.submitted_by} on {self.created_at.strftime('%Y-%m-%d')}"
        )


class MonitoredService(models.Model):
    SERVICE_TYPES = (
        ("Website", "Website"),
        ("Game", "Game"),
    )
    STATUS_CHOICES = (
        ("Up", "Up"),
        ("Degraded", "Degraded"),
        ("Down", "Down"),
    )
    name = models.CharField(max_length=100)
    service_type = models.CharField(
        max_length=50, choices=SERVICE_TYPES, default="Website"
    )
    target = models.CharField(max_length=255, help_text="URL or IP Address to ping")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Up")
    latency_ms = models.IntegerField(null=True, blank=True)
    last_checked = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.status})"


class MessageTemplate(models.Model):
    TEMPLATE_TYPES = (
        ("SMS", "SMS"),
        ("EMAIL", "Email"),
        ("TEXT", "Text Template"),
    )
    name = models.CharField(
        max_length=100, unique=True, help_text="e.g. 'Payment Success'"
    )
    type = models.CharField(max_length=10, choices=TEMPLATE_TYPES)
    subject = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Subject line (for emails only)",
    )
    body = models.TextField(
        help_text="Message content. Supported placeholders: {customer_name}, {paid_amount}, {new_expiration}"
    )

    def __str__(self):
        return f"{self.name} ({self.type})"


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
                "full_name": f"{instance.first_name} {instance.last_name}".strip()
                or instance.username,
                "email": instance.email or f"{instance.username}@example.com",
                "role": "Admin",
                "status": "Active" if instance.is_active else "Inactive",
                "password_hash": "managed_by_django",
            },
        )
        if not was_created:
            updated = False
            if sys_admin.role != "Admin":
                sys_admin.role = "Admin"
                updated = True
            if sys_admin.status != ("Active" if instance.is_active else "Inactive"):
                sys_admin.status = "Active" if instance.is_active else "Inactive"
                updated = True
            if updated:
                sys_admin.save(update_fields=["role", "status"])
