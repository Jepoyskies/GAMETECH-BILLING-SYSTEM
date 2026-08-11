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
    If the customer is active, they get their standard profile.
    If they are expired/suspended, they get the 'expired' profile, and any active session is dropped.
    """
    if not instance.mikrotik_device or not instance.username or not instance.pppoe_password:
        return  # Missing critical info, can't sync

    try:
        api = MikrotikAPI(instance.mikrotik_device)
        
        # Determine the target profile based on status
        target_profile = instance.pppoe_profile or 'default'
        
        # Override profile for restricted statuses
        if instance.status in ['expired', 'suspended', 'inactive', 'past_due']:
            target_profile = 'expired'
            
        # 1. Update the secret on the router
        success, msg = api.add_pppoe_user(
            name=instance.username, 
            password=instance.pppoe_password, 
            profile=target_profile
        )
        
        if success:
            logger.info(f"Successfully synced {instance.username} to {target_profile} profile.")
        else:
            logger.error(f"Failed to sync {instance.username}: {msg}")
            
        # 2. If they are restricted now, forcibly kick any active session so they get the new profile
        if target_profile == 'expired':
            api.remove_active_pppoe_user(instance.username)
            
    except Exception as e:
        logger.error(f"Error syncing customer {instance.username} to Mikrotik: {e}")
