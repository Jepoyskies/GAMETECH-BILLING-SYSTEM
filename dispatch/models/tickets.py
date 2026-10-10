from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from billing.models import Customer, Agent

from .core import Team, Technician, ConfigOption


class JobTicket(models.Model):
    TICKET_TYPE_CHOICES = (
        ('INSTALLATION', 'New Installation'),
        ('REPAIR', 'Repair / Client Concern'),
        ('CIGNAL', 'Cignal Play / Box'),
        ('MIGRATION', 'Plan / Line Migration'),
        ('RELOCATION', 'Relocation / Transfer'),
        ('PULL_OUT', 'Pull Out / Disconnection'),
        ('SITE_VISIT', 'Site Visit'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending Dispatch'),
        ('ASSIGNED', 'Assigned / Scheduled'),
        ('IN_PROGRESS', 'In Progress / On Site'),
        ('COMPLETED', 'Completed (Awaiting QA)'),
        ('QA_PASSED', 'QA Passed (Awaiting Approval)'),
        ('APPROVED', 'Admin Approved / Closed'),
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
    PAYMENT_METHOD_CHOICES = (
        ('CASH', 'Cash'),
        ('GCASH', 'GCash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('OTHER', 'Other'),
    )
    CANCELLATION_REASON_CHOICES = (
        ('no_contact', 'Client Unreachable (No Contact)'),
        ('change_of_mind', 'Change of Mind'),
        ('undecided', 'Undecided'),
        ('other', 'Other'),
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
    sales_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name='job_tickets')
    is_test_data = models.BooleanField(default=False, help_text="Flags test job tickets")
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
    ont_modem_mac = models.CharField(
        max_length=17, null=True, blank=True,
        help_text="Home modem MAC captured by the technician at final submission (AA:BB:CC:DD:EE:FF)"
    )
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
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='CASH', blank=True, null=True, db_index=True)
    payment_collected = models.CharField(max_length=50, blank=True, null=True)
    qa_notes = models.TextField(blank=True, null=True)
    qa_completed_at = models.DateTimeField(null=True, blank=True)

    # No-Contact Escalation Workflow
    contact_attempt_count = models.PositiveSmallIntegerField(default=0, help_text="Number of times technician tried to reach client (max 3)")
    cancellation_reason = models.CharField(max_length=20, choices=CANCELLATION_REASON_CHOICES, null=True, blank=True)

    # Phase 2 & 4 Operational & Lifecycle Additions
    arrived_at = models.DateTimeField(null=True, blank=True, help_text="When field technician clicked Arrived on site")
    arrival_latitude = models.FloatField(null=True, blank=True, help_text="GPS latitude recorded upon arrival")
    arrival_longitude = models.FloatField(null=True, blank=True, help_text="GPS longitude recorded upon arrival")
    finished_at = models.DateTimeField(null=True, blank=True, help_text="When field technician clicked Done on site")
    technician_report = models.TextField(null=True, blank=True, help_text="Work done report entered by technician")
    timer_corrected_at = models.DateTimeField(null=True, blank=True, help_text="When dispatcher corrected timer")
    timer_corrected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='timer_corrected_tickets')
    timer_correction_reason = models.TextField(null=True, blank=True, help_text="Mandatory reason for manual timer adjustment")
    qa_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='qa_reviewed_tickets')
    client_called_by_qa = models.BooleanField(default=False, help_text="Checked if QA dispatcher called client for verification")
    client_agent_informed = models.BooleanField(default=False, help_text="Checked by dispatch when informing client's agent of unreachable/cancellation")
    admin_approved_at = models.DateTimeField(null=True, blank=True, help_text="When admin signed off on job completion")
    admin_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_approved_tickets')
    close_reason = models.CharField(max_length=50, blank=True, null=True, help_text="Undecided, Change of mind, Unreachable, Other")
    close_reason_note = models.TextField(blank=True, null=True)
    same_person_flag = models.BooleanField(default=False, db_index=True, help_text="Flagged if same actor handled multiple stages")
    same_person_stages = models.JSONField(default=list, blank=True, help_text="List of stage names handled by the same person")
    bounce_count = models.PositiveIntegerField(default=0, help_text="Number of times this ticket has been bounced back")
    repeated_bounce_alert = models.BooleanField(default=False, help_text="Flagged when ticket bounces 2 or more times")
    is_flagged = models.BooleanField(default=False, help_text="Flagged for manual administrative review")

    # Audit & Dispatcher Tracking
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dispatched_tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def can_transition_to(self, target_status):
        """
        Validates whether transitioning from self.status to target_status is allowed.
        Enforces lifecycle rules for installations, repairs, and site visits.
        """
        if self.status == target_status:
            return True

        allowed = {
            'PENDING': ['ASSIGNED', 'CANCELLED'],
            'ASSIGNED': ['IN_PROGRESS', 'PENDING', 'CANCELLED'],
            'IN_PROGRESS': ['COMPLETED', 'ASSIGNED', 'CANCELLED'],
            'COMPLETED': ['QA_PASSED', 'APPROVED', 'ASSIGNED', 'IN_PROGRESS', 'CANCELLED'],
            'QA_PASSED': ['APPROVED', 'COMPLETED', 'ASSIGNED', 'IN_PROGRESS', 'CANCELLED'],
            'APPROVED': ['CANCELLED'],
            'CANCELLED': ['PENDING'],
        }

        # Site visits go assign -> in_progress -> completed (skipping QA & admin approval)
        if self.ticket_type == 'SITE_VISIT' and self.status == 'IN_PROGRESS' and target_status in ['COMPLETED', 'APPROVED']:
            return True

        return target_status in allowed.get(self.status, [])

    def record_stage_action(self, stage_name, user):
        """
        Tracks the actor of a pipeline stage and flags same-person handling across multiple stages.
        """
        if not user or not user.is_authenticated:
            return

        stages = list(self.same_person_stages or [])
        user_id_str = str(user.id)
        current_entry = f"{stage_name}:{user_id_str}"
        if current_entry not in stages:
            stages.append(current_entry)
            self.same_person_stages = stages

        # Check if this user handled distinct stages
        distinct_stages = set()
        for s in stages:
            if ":" in s:
                stg, uid = s.split(":", 1)
                if uid == user_id_str:
                    distinct_stages.add(stg)
        if len(distinct_stages) >= 2:
            self.same_person_flag = True

    # ── Job-order credit (Sir's rule, DERIVED — never stored) ─────────────
    # A ticket only scores once it reaches APPROVED. The person who opened it
    # earns 1; the person who closed it earns 1. Same person on both ends
    # therefore earns 2, which is exactly the rule, with no counter to drift.
    # Cancelled / still-open / bounced tickets score 0 on purpose: credit
    # pays for work that was actually finished and signed off.

    @property
    def credit_earns(self):
        """True only when this ticket has been closed and signed off."""
        return self.status == 'APPROVED'

    @property
    def opener_credit(self):
        return 1 if (self.credit_earns and self.created_by_id) else 0

    @property
    def closer_credit(self):
        return 1 if (self.credit_earns and self.admin_approved_by_id) else 0

    @property
    def total_credit(self):
        return self.opener_credit + self.closer_credit

    @property
    def credit_summary(self):
        """Human-readable 'Opened by X → Closed by Y (2 pts)' for the ticket page."""
        opened = self.created_by.get_full_name() or self.created_by.username if self.created_by_id else None
        closed = (self.admin_approved_by.get_full_name() or self.admin_approved_by.username) if self.admin_approved_by_id else None
        if not self.credit_earns:
            return {'opened_by': opened, 'closed_by': closed, 'points': 0, 'same_person': False, 'earned': False}
        return {
            'opened_by': opened,
            'closed_by': closed,
            'points': self.total_credit,
            'same_person': bool(self.created_by_id and self.created_by_id == self.admin_approved_by_id),
            'earned': True,
        }

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

    @property
    def turnaround_display(self):
        end_time = self.time_accomplish or self.done_at
        if self.duration:
            mins = self.duration
            if mins < 60:
                return f"{mins}m"
            hours = mins // 60
            rem_mins = mins % 60
            return f"{hours}h {rem_mins}m" if rem_mins else f"{hours}h"
        if self.time_start and end_time:
            delta = end_time - self.time_start
            total_mins = int(delta.total_seconds() // 60)
            if total_mins < 60:
                return f"{total_mins}m"
            hours = total_mins // 60
            rem_mins = total_mins % 60
            return f"{hours}h {rem_mins}m" if rem_mins else f"{hours}h"
        if self.created_at and end_time:
            delta = end_time - self.created_at
            total_mins = int(delta.total_seconds() // 60)
            if total_mins < 60:
                return f"{total_mins}m"
            hours = total_mins // 60
            rem_mins = total_mins % 60
            if hours < 24:
                return f"{hours}h {rem_mins}m" if rem_mins else f"{hours}h"
            days = hours // 24
            rem_hours = hours % 24
            return f"{days}d {rem_hours}h" if rem_hours else f"{days}d"
        return "In Progress" if self.status in ['ASSIGNED', 'IN_PROGRESS'] else "-"

    class Meta:
        ordering = ['-created_at']
        permissions = [
            ('assign_technicians', 'Can assign technicians to job tickets'),
            ('technician_job_actions', 'Can execute field technician mobile job actions'),
            ('correct_timers', 'Can adjust technician arrived/done timers'),
            ('dispatch_qa', 'Can review field reports and QA job tickets'),
            ('admin_approve', 'Can grant final admin sign-off on jobs'),
            ('view_bounce_summary', 'Can view bounce-back summary and pattern metrics'),
        ]

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            from dispatch.utils import generate_ticket_number
            from django.db import IntegrityError, transaction
            import time

            max_retries = 5
            for attempt in range(max_retries):
                self.ticket_number = generate_ticket_number(self.ticket_type)
                try:
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    if attempt == max_retries - 1:
                        raise
                    self.ticket_number = None
                    time.sleep(0.05 * (attempt + 1))
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_number} - {self.client_name} ({self.get_status_display()})"


class TicketTechnicianAssignment(models.Model):
    """
    Ordered technician handover history for a job ticket.

    JobTicket.technicians is a flat M2M: it cannot say who was first, who came
    in next, or why. This table is the ordered record. `sequence` starts at 1;
    the row with is_current=True is the technician(s) on the job right now. When
    a tech is replaced the old row is closed off with replacement_reason (a
    ConfigOption, mandatory) and the new tech gets the next sequence.
    """

    job_ticket = models.ForeignKey(JobTicket, on_delete=models.CASCADE, related_name='tech_assignments')
    technician = models.ForeignKey(Technician, on_delete=models.CASCADE, related_name='ticket_assignments')
    sequence = models.PositiveSmallIntegerField(default=1)
    assigned_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    is_current = models.BooleanField(default=True, db_index=True)

    # Set on the OUTGOING row when this technician is replaced.
    replaced_by = models.ForeignKey(
        Technician, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='replaces_assignments'
    )
    replacement_reason = models.ForeignKey(
        ConfigOption, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='replacement_reasons'
    )
    replacement_note = models.TextField(
        null=True, blank=True,
        help_text="Required when the replacement reason is 'Other'."
    )
    replaced_by_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='technician_replacements_made'
    )

    class Meta:
        ordering = ['job_ticket_id', 'sequence']
        unique_together = ('job_ticket', 'technician', 'sequence')

    def __str__(self):
        return f"{self.job_ticket.ticket_number} #{self.sequence} {self.technician.name}"

    @property
    def stage_label(self):
        if self.finished_at and self.replaced_by_id:
            return "replaced"
        if self.finished_at:
            return "finished"
        if self.started_at:
            return "started"
        return "assigned"

    @property
    def reason_display(self):
        if self.replacement_reason_id:
            return self.replacement_reason.label
        return None


class JobTicketHistory(models.Model):
    job_ticket = models.ForeignKey(JobTicket, on_delete=models.CASCADE, related_name='history_logs')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    note = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.job_ticket.ticket_number} transitioned to {self.to_status} at {self.timestamp}"


class TicketBounceHistory(models.Model):
    BOUNCE_TYPE_CHOICES = (
        ('revisit', 'Revisit with new timer'),
        ('correct_report', 'Correct the report'),
        ('admin_to_dispatch', 'Admin returned to Dispatch QA'),
    )
    ticket = models.ForeignKey(JobTicket, on_delete=models.CASCADE, related_name='bounces')
    from_stage = models.CharField(max_length=50)
    to_stage = models.CharField(max_length=50)
    bounce_type = models.CharField(max_length=50, choices=BOUNCE_TYPE_CHOICES, default='correct_report')
    reason = models.TextField(help_text="Mandatory reason for bouncing ticket back")
    bounced_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bounced_tickets')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Bounce on {self.ticket.ticket_number} ({self.from_stage} -> {self.to_stage}) by {self.bounced_by}"


class CallAttemptLog(models.Model):
    RESULT_CHOICES = (
        ('unanswered', 'Unanswered'),
        ('rejected', 'Rejected / Call Declined'),
        ('busy', 'Line Busy'),
        ('client_declined', 'Client Declined / Cancelled'),
        ('other', 'Other'),
    )
    ticket = models.ForeignKey(JobTicket, on_delete=models.CASCADE, related_name='call_attempts')
    technician = models.ForeignKey(Technician, on_delete=models.SET_NULL, null=True, blank=True, related_name='call_attempts')
    attempt_number = models.PositiveSmallIntegerField(help_text="1st, 2nd, 3rd call attempt")
    attempt_time = models.DateTimeField(default=timezone.now)
    result = models.CharField(max_length=50, choices=RESULT_CHOICES, default='unanswered')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['attempt_number', 'attempt_time']

    def __str__(self):
        return f"Attempt {self.attempt_number} for {self.ticket.ticket_number}: {self.get_result_display()}"