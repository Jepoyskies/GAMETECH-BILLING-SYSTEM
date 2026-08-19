import logging
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from .models import Customer
from network_manager.services import MikrotikAPI

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Customer)
def track_customer_changes(sender, instance, **kwargs):
    if instance.pk:
        orig = Customer.objects.filter(pk=instance.pk).first()
        if orig:
            instance._original_plan_id = orig.plan_id
            instance._original_mikrotik_device_id = orig.mikrotik_device_id
    else:
        instance._original_plan_id = None
        instance._original_mikrotik_device_id = None

@receiver(post_save, sender=Customer)
def sync_customer_to_mikrotik(sender, instance, created, **kwargs):
    """
    Syncs the customer's PPPoE secret to their assigned Mikrotik device when saved.
    """
    if not instance.mikrotik_device or not instance.pppoe_username or not instance.pppoe_password:
        return  # Missing critical info, can't sync

    # --- NEW LOGIC: Router Transfer Orphan Cleanup ---
    if getattr(instance, '_original_mikrotik_device_id', None) is not None:
        if instance._original_mikrotik_device_id != instance.mikrotik_device_id:
            try:
                from network_manager.models import MikrotikDevice
                old_device = MikrotikDevice.objects.filter(pk=instance._original_mikrotik_device_id).first()
                if old_device:
                    old_api = MikrotikAPI(old_device)
                    # This removes the secret and kicks the active session
                    old_api.delete_pppoe_user(instance.pppoe_username)
            except Exception as e:
                logger.warning(f"Failed to cleanup orphaned PPPoE user {instance.pppoe_username} on old router: {e}")
                # We do not return here. We allow the signal to continue and provision on the NEW router.
    # --------------------------------------------------

    try:
        api = MikrotikAPI(instance.mikrotik_device)

        # 1. Determine target profile from SubscriptionPlan
        target_profile = instance.plan.name if instance.plan else "default"
        is_disabled = "no"

        # 2. Update the secret on the router with standard profile
        success, msg = api.add_pppoe_user(
            name=instance.pppoe_username,
            password=instance.pppoe_password,
            profile=target_profile,
            disabled=is_disabled
        )

        # 3. Plan Upgrade Session Kick
        # If the plan changed, and the user is active, bounce their session to apply speeds
        if getattr(instance, '_original_plan_id', None) != instance.plan_id:
            if instance.status == 'active':
                api.kick_active_user(instance.pppoe_username)

        # 4. Apply Suspension/Reactivation Logic (Option C)
        if instance.status in ['expired', 'suspended', 'inactive', 'past_due']:
            api.suspend_pppoe_user(instance.pppoe_username)
        else:
            api.enable_pppoe_user(instance.pppoe_username)

        # 5. Mark as Synced
        Customer.objects.filter(pk=instance.pk).update(sync_status='Synced')

    except Exception as e:
        logger.error(f"Error syncing customer {instance.pppoe_username} to Mikrotik: {e}")
        # Mark as Failed (Router Unreachable)
        Customer.objects.filter(pk=instance.pk).update(sync_status='Failed')

@receiver(post_delete, sender=Customer)
def delete_customer_from_mikrotik(sender, instance, **kwargs):
    """
    When a Customer is deleted in Django, remove their PPP secret and any bridge drop rules from their Mikrotik device.
    """
    if not instance.mikrotik_device or not instance.pppoe_username:
        return
        
    try:
        api = MikrotikAPI(instance.mikrotik_device)
        api.delete_pppoe_user(instance.pppoe_username)
    except Exception as e:
        logger.error(f"Error deleting customer {instance.pppoe_username} from Mikrotik: {e}")

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

from django.contrib.auth.models import User
from .models import EmployeeProfile

@receiver(post_save, sender=User)
def create_employee_profile(sender, instance, created, **kwargs):
    """
    Automatically create an EmployeeProfile when a new User is created.
    """
    if created:
        EmployeeProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_employee_profile(sender, instance, **kwargs):
    """
    Save the EmployeeProfile when the User is saved.
    """
    if hasattr(instance, 'employee_profile'):
        instance.employee_profile.save()

