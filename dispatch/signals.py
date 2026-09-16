import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from billing.models import Customer
from .models import JobTicket

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Customer)
def auto_create_dispatch_ticket_on_pending_install(sender, instance, created, **kwargs):
    """
    Smart CRM Hook:
    If a Customer is created or updated and their status or installation_status is 'pending'
    (New Applicant), automatically generate a JobTicket with type 'New Installation' in the Dispatch queue.
    """
    if kwargs.get('raw'):
        return

    is_pending = (instance.status == 'pending' or instance.installation_status == 'pending')

    if not is_pending:
        return

    # Extract scheduled installation date from customer's installed_at
    sched_date = None
    if instance.installed_at:
        sched_date = instance.installed_at.date() if hasattr(instance.installed_at, 'date') else instance.installed_at

    # Idempotency check: Do not create duplicate open installation tickets for the same customer
    existing_ticket = JobTicket.objects.filter(
        customer=instance,
        ticket_type='INSTALLATION',
        status__in=['PENDING', 'ASSIGNED', 'IN_PROGRESS']
    ).first()

    if existing_ticket:
        # Keep client details in sync if anything changed
        updated = False
        if instance.full_name and existing_ticket.client_name != instance.full_name:
            existing_ticket.client_name = instance.full_name
            updated = True
        if instance.address and existing_ticket.address != instance.address:
            existing_ticket.address = instance.address
            updated = True
        if instance.phone and existing_ticket.contact_number != instance.phone:
            existing_ticket.contact_number = instance.phone
            updated = True
        if instance.mikrotik_device and existing_ticket.mikrotik_device != instance.mikrotik_device:
            existing_ticket.mikrotik_device = instance.mikrotik_device
            updated = True
        if instance.latitude and existing_ticket.latitude != float(instance.latitude):
            existing_ticket.latitude = float(instance.latitude)
            updated = True
        if instance.longitude and existing_ticket.longitude != float(instance.longitude):
            existing_ticket.longitude = float(instance.longitude)
            updated = True
        if sched_date and existing_ticket.scheduled_date != sched_date:
            existing_ticket.scheduled_date = sched_date
            updated = True
        if updated:
            existing_ticket.save()
        return

    # Extract clean details from customer instance
    barangay_name = instance.barangay.name if instance.barangay else ''
    agent_name = instance.agent.name if instance.agent else ''
    plan_name = instance.plan.name if instance.plan else 'Pending Selection'
    lat = float(instance.latitude) if instance.latitude else None
    lng = float(instance.longitude) if instance.longitude else None

    concern_text = f"New Applicant Internet Installation — Plan: {plan_name}"
    if barangay_name:
        concern_text += f" ({barangay_name})"

    new_ticket = JobTicket.objects.create(
        ticket_type='INSTALLATION',
        status='PENDING',
        priority='NORMAL',
        source_tab='INTERNET_INSTALL',
        customer=instance,
        mikrotik_device=instance.mikrotik_device,
        client_name=instance.full_name,
        address=instance.address or '',
        barangay=barangay_name,
        contact_number=instance.phone or '',
        account_no=instance.pppoe_username or '',
        sales_agent=agent_name,
        plan_package=plan_name,
        concern=concern_text,
        chat_type='Walk-In / CRM Application',
        latitude=lat,
        longitude=lng,
        scheduled_date=sched_date,
    )
    logger.info(
        f"[DISPATCH] Auto-created JobTicket {new_ticket.ticket_number} for customer {instance.full_name} (ID: {instance.id})"
    )
