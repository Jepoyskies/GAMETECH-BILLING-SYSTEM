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
            instance._original_state = {
                'Full Name': orig.full_name,
                'Email': orig.email,
                'Phone': orig.phone,
                'Status': orig.status,
                'Plan': orig.plan.name if orig.plan else "None",
                'Router': orig.mikrotik_device.device_name if orig.mikrotik_device else "None",
                'Username': orig.pppoe_username,
                'Password': orig.pppoe_password,
                'Expiration': orig.expires_at.strftime('%Y-%m-%d %H:%M') if orig.expires_at else "None"
            }
    else:
        instance._original_plan_id = None
        instance._original_mikrotik_device_id = None
        instance._original_state = None

@receiver(post_save, sender=Customer)
def sync_customer_to_mikrotik(sender, instance, created, **kwargs):
    """
    Syncs the customer's PPPoE secret to their assigned Mikrotik device when saved.
    """
    if not instance.mikrotik_device or not instance.pppoe_username or not instance.pppoe_password:
        return  # Missing critical info, can't sync

    # --- NEW LOGIC: Skip sync if no Mikrotik-relevant fields changed ---
    if not created and hasattr(instance, '_original_state') and instance._original_state:
        new_state = {
            'Full Name': instance.full_name,
            'Status': instance.status,
            'Plan': instance.plan.name if instance.plan else "None",
            'Router': instance.mikrotik_device.device_name if instance.mikrotik_device else "None",
            'Username': instance.pppoe_username,
            'Password': instance.pppoe_password,
        }
        changed = False
        for key in new_state:
            if str(instance._original_state.get(key)) != str(new_state.get(key)):
                changed = True
                break
                
        if not changed:
            # None of the fields relevant to Mikrotik changed (e.g. Cignal update)
            return
    # -------------------------------------------------------------------

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

        # --- NEW LOGIC: Handle Offboarding / Pull Out ---
        if instance.status == 'pull out':
            api.delete_pppoe_user(instance.pppoe_username)
            Customer.objects.filter(pk=instance.pk).update(sync_status='Synced')
            return
        # ------------------------------------------------

        # 1. Determine target profile from SubscriptionPlan
        target_profile = instance.plan.name if instance.plan else "default"
        is_disabled = "no"
        
        # Fetch latest payment for comment logic
        latest_payment = instance.payments.order_by('-created_at').first()
        
        comment_parts = []
        if latest_payment:
            paid_str = latest_payment.created_at.strftime('%b %d, %Y')
            expiry_str = instance.expires_at.strftime('%b %d, %Y') if instance.expires_at else "None"
            plan_name = instance.plan.name if instance.plan else "No Plan"
            payment_method = latest_payment.payment_method
            admin_name = latest_payment.adjusted_by if latest_payment.adjusted_by else "Admin"
            reason = latest_payment.reason if latest_payment.reason else ""
            
            pay_comment = f"paid {paid_str} exp {expiry_str} . {plan_name} . {payment_method} . {admin_name}"
            if reason:
                pay_comment += f" . {reason}"
            comment_parts.append(pay_comment)

        # Add Profile Details
        profile_parts = [str(instance.full_name) if instance.full_name else "Unknown"]
        
        if instance.phone:
            profile_parts.append(str(instance.phone))
            
        if not latest_payment and instance.expires_at:
            profile_parts.append(f"Exp: {instance.expires_at.strftime('%Y-%m-%d')}")
            
        if instance.barangay and instance.barangay.name:
            profile_parts.append(str(instance.barangay.name))
        elif instance.address:
            # truncate address if it's too long, safely converting to string
            clean_addr = str(instance.address).replace('\n', ' ').replace('\r', ' ')
            profile_parts.append(clean_addr[:30] + ('...' if len(clean_addr) > 30 else ''))
            
        comment_parts.append(" | ".join(profile_parts))
        secret_comment = " || ".join(comment_parts)
        
        # Final cleanup for Mikrotik comment compatibility (remove non-printable chars)
        secret_comment = "".join(c for c in secret_comment if c.isprintable())

        # 2. Update the secret on the router with standard profile
        success_add, msg_add = api.add_pppoe_user(
            name=instance.pppoe_username,
            password=instance.pppoe_password,
            profile=target_profile,
            comment=secret_comment,
            disabled=is_disabled
        )
        
        if not success_add:
            raise Exception(f"Failed to add PPPoE user: {msg_add}")

        # 3. Plan Upgrade Session Kick
        # If the plan changed, and the user is active, bounce their session to apply speeds
        if getattr(instance, '_original_plan_id', None) != instance.plan_id:
            if instance.status == 'active':
                api.kick_active_user(instance.pppoe_username)

        # 4. Apply Suspension/Reactivation Logic (Option C)
        if instance.status in ['expired', 'suspended', 'inactive', 'past_due']:
            success_status, msg_status = api.suspend_pppoe_user(instance.pppoe_username)
        else:
            success_status, msg_status = api.enable_pppoe_user(instance.pppoe_username)
            
        if not success_status:
            logger.warning(f"Failed to change status for {instance.pppoe_username}: {msg_status}")
            # We don't raise here because the user is already on the router. It might just be an issue with bridge filter.

        # 5. Mark as Synced
        Customer.objects.filter(pk=instance.pk).update(sync_status='Synced')

    except Exception as e:
        logger.error(f"Error syncing customer {instance.pppoe_username} to Mikrotik: {e}")
        # Mark as Failed (Router Unreachable)
        Customer.objects.filter(pk=instance.pk).update(sync_status='Failed')

@receiver(post_save, sender=Customer)
def audit_customer_changes(sender, instance, created, **kwargs):
    """
    Logs changes to Customer fields into SystemLog for audit purposes.
    """
    from billing.models import SystemLog
    
    # We only log updates, not creations (unless we want to, but updates are more critical for audits)
    if not created and hasattr(instance, '_original_state') and instance._original_state:
        changes = []
        new_state = {
            'Full Name': instance.full_name,
            'Email': instance.email,
            'Phone': instance.phone,
            'Status': instance.status,
            'Plan': instance.plan.name if instance.plan else "None",
            'Router': instance.mikrotik_device.device_name if instance.mikrotik_device else "None",
            'Username': instance.pppoe_username,
            'Password': instance.pppoe_password,
            'Expiration': instance.expires_at.strftime('%Y-%m-%d %H:%M') if instance.expires_at else "None"
        }
        
        for field, old_val in instance._original_state.items():
            new_val = new_state.get(field)
            if str(old_val) != str(new_val):
                changes.append(f"{field}: '{old_val}' \u2192 '{new_val}'")
                
        if changes:
            from billing.middleware import get_current_user
            current_user = get_current_user()
            
            # If changed_by_user was explicitly injected into the model instance, use that.
            # Otherwise, use the thread local user. Otherwise fallback to System/Admin.
            if hasattr(instance, '_changed_by_user'):
                changed_by_user = instance._changed_by_user
            elif current_user and current_user.is_authenticated:
                changed_by_user = current_user.username
            else:
                changed_by_user = 'System/Admin'

            SystemLog.objects.create(
                table_name='Customer',
                record_id=str(instance.id),
                action='UPDATE (Profile)',
                changed_by=changed_by_user,
                target_name=instance.full_name,
                old_data="\n".join(changes),
                new_data="Profile updated via UI or API"
            )

@receiver(post_save, sender=Customer)
def notify_customer_status_change(sender, instance, created, **kwargs):
    """
    Creates a high-priority system notification when a customer is suspended or expired.
    """
    if not created and hasattr(instance, '_original_state') and instance._original_state:
        old_status = instance._original_state.get('Status')
        new_status = instance.status
        
        if old_status != new_status and new_status in ['suspended', 'expired']:
            from billing.models import Notification
            from django.urls import reverse
            try:
                customer_url = reverse('view_customer', args=[instance.id])
                Notification.objects.create(
                    title=f"Customer {new_status.title()}",
                    message=f"{instance.full_name}'s account has been marked as {new_status}.",
                    notification_type="network", # network type triggers high-priority UI
                    link=customer_url
                )
            except Exception as e:
                logger.error(f"Failed to create status notification for {instance.full_name}: {e}")

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
    If the name was changed, delete the old profile first.
    """
    devices = MikrotikDevice.objects.all()
    for device in devices:
        try:
            api = MikrotikAPI(device)
            
            # Check if name was changed
            if hasattr(instance, '_original_name') and instance._original_name and instance._original_name != instance.name:
                try:
                    api.delete_plan_from_mikrotik(plan_name=instance._original_name)
                except Exception as e:
                    logger.warning(f"Could not delete old plan {instance._original_name} from {device.device_name} during rename: {e}")

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

from django.contrib.auth.signals import user_logged_in

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Keep a historical record of when admins log in.
    """
    from billing.models import SystemLog
    
    # Get IP if possible
    ip_addr = 'Unknown'
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_addr = x_forwarded_for.split(',')[0]
        else:
            ip_addr = request.META.get('REMOTE_ADDR', 'Unknown')
            
    SystemLog.objects.create(
        table_name='User',
        record_id=str(user.id),
        action='LOGIN',
        changed_by=user.username,
        target_name=user.username,
        old_data=f'IP: {ip_addr}',
        new_data='User successfully logged in.'
    )

