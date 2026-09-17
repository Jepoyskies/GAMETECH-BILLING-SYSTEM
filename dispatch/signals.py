import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from billing.models import Customer
from .models import JobTicket

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Customer)
def auto_create_dispatch_ticket_on_pending_install(sender, instance, created, **kwargs):
    """
    Smart CRM Hook (Direction 1: CRM -> Dispatch):
    - If a Customer's status or installation_status is 'pending', automatically generate
      or update an open JobTicket ('INSTALLATION') in the Dispatch queue.
    - If a Customer's installation_status is 'installed', automatically complete any open
      installation tickets for this customer.
    """
    if kwargs.get('raw'):
        return

    is_pending = (instance.status == 'pending' or instance.installation_status == 'pending')

    # If customer is marked installed, auto-complete any remaining open installation tickets
    if not is_pending:
        if instance.installation_status == 'installed':
            open_tickets = JobTicket.objects.filter(
                customer=instance,
                ticket_type='INSTALLATION',
                status__in=['PENDING', 'ASSIGNED', 'IN_PROGRESS']
            )
            for t in open_tickets:
                t.status = 'COMPLETED'
                t.done_at = instance.installed_at or timezone.now()
                t.time_accomplish = t.done_at
                completed_note = f"Line marked installed & activated via CRM on {t.done_at.strftime('%Y-%m-%d %H:%M')}"
                if t.actions_taken:
                    t.actions_taken += f" | {completed_note}"
                else:
                    t.actions_taken = completed_note
                t.save()
                logger.info(f"[DISPATCH] Auto-completed JobTicket {t.ticket_number} for installed customer {instance.full_name}")
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
        sales_agent=instance.agent,
        is_test_data=instance.is_test_data,
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


@receiver(post_save, sender=JobTicket)
def sync_ticket_completion_to_customer(sender, instance, created, **kwargs):
    """
    Smart CRM Hook (Direction 2: Dispatch -> CRM):
    When a JobTicket with ticket_type='INSTALLATION' is marked 'COMPLETED',
    automatically transition the linked customer's installation_status to 'installed',
    set installed_at, promote status to 'active', and record modem MAC/SN if available.
    """
    if kwargs.get('raw'):
        return

    if instance.ticket_type == 'INSTALLATION' and instance.status == 'COMPLETED' and instance.customer:
        customer = instance.customer
        fields_to_update = []

        if customer.installation_status != 'installed':
            customer.installation_status = 'installed'
            fields_to_update.append('installation_status')

        if not customer.installed_at:
            customer.installed_at = instance.done_at or timezone.now()
            fields_to_update.append('installed_at')

        if customer.status == 'pending':
            customer.status = 'active'
            fields_to_update.append('status')

        if instance.ont_modem_sn and not customer.mac_address:
            customer.mac_address = instance.ont_modem_sn
            fields_to_update.append('mac_address')

        if fields_to_update:
            customer.save(update_fields=fields_to_update)
            logger.info(
                f"[DISPATCH] Promoted Customer {customer.full_name} (ID: {customer.id}) to installed & active from completed ticket {instance.ticket_number}"
            )

