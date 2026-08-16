import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Customer
from network_manager.services import MikrotikAPI

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Customer)
def sync_customer_to_mikrotik(sender, instance, created, **kwargs):
    """
    Syncs the customer's PPPoE secret to their assigned Mikrotik device when saved.
    """
    if not instance.mikrotik_device or not instance.pppoe_username or not instance.pppoe_password:
        return  # Missing critical info, can't sync

    try:
        api = MikrotikAPI(instance.mikrotik_device)

        # 1. Determine target profile from SubscriptionPlan
        target_profile = instance.plan.name if instance.plan else "default"
        
        # 2. Determine if user should be disabled (Now Option C: MAC-Level Bridge Drop)
        is_disabled = "no"

        # 3. Update the secret on the router with standard profile
        success, msg = api.add_pppoe_user(
            name=instance.pppoe_username,
            password=instance.pppoe_password,
            profile=target_profile,
            disabled=is_disabled
        )

        if success:
            logger.info(
                f"Successfully synced {instance.pppoe_username} to {target_profile} profile.")
        else:
            logger.error(f"Failed to sync {instance.pppoe_username}: {msg}")

        # 4. Apply Suspension/Reactivation Logic (Option C)
        if instance.status in ['expired', 'suspended', 'inactive', 'past_due']:
            api.suspend_pppoe_user(instance.pppoe_username)
        else:
            api.enable_pppoe_user(instance.pppoe_username)

    except Exception as e:
        logger.error(
            f"Error syncing customer {instance.pppoe_username} to Mikrotik: {e}")

from .models import SubscriptionPlan
from network_manager.models import MikrotikDevice

@receiver(post_save, sender=SubscriptionPlan)
def sync_plan_on_save(sender, instance, created, **kwargs):
    """
    When a SubscriptionPlan is saved in Django, push it to all active Mikrotik devices.
    """
    devices = MikrotikDevice.objects.all()
    for device in devices:
        try:
            api = MikrotikAPI(device)
            api.sync_plan_to_mikrotik(
                plan_name=instance.name,
                speed_up=instance.speed_up,
                speed_down=instance.speed_down
            )
        except Exception as e:
            logger.error(f"Failed to sync plan {instance.name} to {device.device_name}: {e}")

from django.db.models.signals import post_delete

@receiver(post_delete, sender=SubscriptionPlan)
def delete_plan_on_mikrotik(sender, instance, **kwargs):
    """
    When a SubscriptionPlan is deleted in Django, remove it from all active Mikrotik devices.
    """
    devices = MikrotikDevice.objects.all()
    for device in devices:
        try:
            api = MikrotikAPI(device)
            api.delete_plan_from_mikrotik(plan_name=instance.name)
        except Exception as e:
            logger.error(f"Failed to delete plan {instance.name} from {device.device_name}: {e}")
