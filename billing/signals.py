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
                "Full Name": orig.full_name,
                "Email": orig.email,
                "Phone": orig.phone,
                "Status": orig.status,
                "Plan": orig.plan.name if orig.plan else "None",
                "Account Type": orig.account_type.type_name if orig.account_type else "None",
                "Barangay": orig.barangay.name if orig.barangay else "None",
                "Agent": orig.agent.name if orig.agent else "None",
                "Router": orig.mikrotik_device.device_name if orig.mikrotik_device else "None",
                "Username": orig.pppoe_username,
                "Password": orig.pppoe_password,
                "Expiration": orig.expires_at.strftime("%Y-%m-%d %H:%M") if orig.expires_at else "None",
            }
    else:
        instance._original_plan_id = None
        instance._original_mikrotik_device_id = None
        instance._original_state = None


def _stage_pending(instance):
    """Mark a customer as needing a deliberate push. Never touches the router.

    Only router-relevant fields count. Saving a phone number or a Cignal
    number must NOT make a customer look unsynced, otherwise the queue fills
    with noise and staff stop trusting it.
    """
    fields = (
        "full_name",
        "status",
        "plan_id",
        "mikrotik_device_id",
        "pppoe_username",
        "pppoe_password",
    )
    orig = getattr(instance, "_original_state", None)

    if orig:
        new_state = {
            "Full Name": instance.full_name,
            "Status": instance.status,
            "Plan": instance.plan.name if instance.plan else "None",
            "Router": (
                instance.mikrotik_device.device_name
                if instance.mikrotik_device
                else "None"
            ),
            "Username": instance.pppoe_username,
            "Password": instance.pppoe_password,
        }
        if all(
            str(orig.get(k)) == str(v) for k, v in new_state.items()
        ):
            return  # Nothing the router cares about changed.

    # `Blocked` is more urgent than `Pending` (it means write mode was off),
    # so never downgrade it here.
    if instance.sync_status == "Blocked":
        return

    Customer.objects.filter(pk=instance.pk).exclude(
        sync_status__in=["Blocked", "Failed"]
    ).update(sync_status="Pending")

    logger.info(
        f"[STAGED] {instance.pppoe_username} needs a deliberate push from the "
        f"Sync Manager. No router write was made."
    )


@receiver(post_save, sender=Customer)
def sync_customer_to_mikrotik(sender, instance, created, **kwargs):
    """
    PUSH-TO-ROUTER: opt-in, never automatic.

    This used to fire on every single Customer save, so the instant staff
    pressed "Save" the PPPoE secret was written to the live router. That is
    dangerous: a typo in a name, a wrong router, or a half-filled form
    becomes a real customer cut off or a real secret on the wrong box, with
    no confirmation step and no undo.

    Now the signal only *stages* the work. A customer whose router-relevant
    details changed is marked "Pending" and a human pushes it from the Sync
    Manager, where the diff is visible first. Set
    `instance.push_to_router = True` to keep the old one-shot behaviour for
    a deliberate, single, confirmed action (used by the reconnect flow).
    """
    if kwargs.get("raw"):
        return

    if (
        getattr(instance, "is_test_data", False)
        or not instance.mikrotik_device
        or not instance.pppoe_username
        or not instance.pppoe_password
    ):
        return  # Skip test accounts or missing critical info

    # --- OPT-OUT: staging only, a human pushes from the Sync Manager ---
    if not getattr(instance, "push_to_router", False):
        _stage_pending(instance)
        return

    # --- NEW LOGIC: Skip sync if no Mikrotik-relevant fields changed ---
    # An explicit push_to_router means "write this now", so it bypasses this
    # optimisation. Without that, a deliberate re-push of an unchanged
    # customer would silently do nothing.
    if (
        not created
        and not getattr(instance, "push_to_router", False)
        and hasattr(instance, "_original_state")
        and instance._original_state
    ):
        new_state = {
            "Full Name": instance.full_name,
            "Status": instance.status,
            "Plan": instance.plan.name if instance.plan else "None",
            "Router": (
                instance.mikrotik_device.device_name
                if instance.mikrotik_device
                else "None"
            ),
            "Username": instance.pppoe_username,
            "Password": instance.pppoe_password,
            "Expiration": (
                instance.expires_at.strftime("%Y-%m-%d %H:%M")
                if instance.expires_at
                else "None"
            ),
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
    if getattr(instance, "_original_mikrotik_device_id", None) is not None:
        if instance._original_mikrotik_device_id != instance.mikrotik_device_id:
            try:
                from network_manager.models import MikrotikDevice

                old_device = MikrotikDevice.objects.filter(
                    pk=instance._original_mikrotik_device_id
                ).first()
                if old_device:
                    old_api = MikrotikAPI(old_device)
                    # Check if immediate session kick was requested (default False preserves session until physical swap)
                    kick_active = getattr(instance, "_kick_active_on_transfer", False)
                    old_api.delete_pppoe_user(instance.pppoe_username, kick_active=kick_active)
            except Exception as e:
                logger.warning(
                    f"Failed to cleanup orphaned PPPoE user {instance.pppoe_username} on old router: {e}"
                )
                # We do not return here. We allow the signal to continue and provision on the NEW router.
    # --------------------------------------------------

    try:
        api = MikrotikAPI(instance.mikrotik_device)

        if getattr(api, "is_read_only", False):
            logger.info(
                f"[ROUTER_MODE=read_only] Router write blocked for customer {instance.pppoe_username}. Marking sync_status='Blocked'."
            )
            Customer.objects.filter(pk=instance.pk).update(sync_status="Blocked")
            return

        # --- NEW LOGIC: Handle Offboarding / Pull Out ---
        if instance.status == "pull out":
            api.delete_pppoe_user(instance.pppoe_username)
            Customer.objects.filter(pk=instance.pk).update(sync_status="Synced")
            return
        # ------------------------------------------------

        # 1. Determine target profile from SubscriptionPlan
        target_profile = instance.plan.name if instance.plan else "default"
        is_disabled = "no"

        # Generate standardized comment from Customer model
        secret_comment = instance.generate_mikrotik_comment()

        # 2. Update the secret on the router with standard profile
        success_add, msg_add = api.add_pppoe_user(
            name=instance.pppoe_username,
            password=instance.pppoe_password,
            profile=target_profile,
            comment=secret_comment,
            disabled=is_disabled,
        )

        if not success_add:
            raise Exception(f"Failed to add PPPoE user: {msg_add}")

        # 3. Plan Upgrade Session Kick
        # If the plan changed, and the user is active, bounce their session to apply speeds
        if getattr(instance, "_original_plan_id", None) != instance.plan_id:
            if instance.status == "active":
                api.kick_active_user(instance.pppoe_username)

        # 4. Apply Suspension/Reactivation Logic (Option C)
        if instance.status in ["expired", "suspended", "inactive", "past_due"]:
            success_status, msg_status = api.suspend_pppoe_user(instance.pppoe_username)
        else:
            success_status, msg_status = api.enable_pppoe_user(instance.pppoe_username)

        if not success_status:
            logger.warning(
                f"Failed to change status for {instance.pppoe_username}: {msg_status}"
            )
            # We don't raise here because the user is already on the router. It might just be an issue with bridge filter.

        # 5. Mark as Synced
        Customer.objects.filter(pk=instance.pk).update(sync_status="Synced")

    except Exception as e:
        logger.error(
            f"Error syncing customer {instance.pppoe_username} to Mikrotik: {e}"
        )
        # Mark as Failed (Router Unreachable)
        Customer.objects.filter(pk=instance.pk).update(sync_status="Failed")


@receiver(post_save, sender=Customer)
def audit_customer_changes(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    """
    Logs changes to Customer fields into SystemLog for audit purposes.
    """
    from billing.models import SystemLog
    from billing.middleware import get_current_user

    current_user = get_current_user()

    # Determine user who made the change
    if hasattr(instance, "_changed_by_user"):
        changed_by_user = instance._changed_by_user
    elif current_user and current_user.is_authenticated:
        changed_by_user = current_user.username
    else:
        changed_by_user = "System/Admin"

    # Log Creation
    if created:
        action_msg = "Create Customer"
        if getattr(instance, "_is_imported", False):
            action_msg = "Import Customer"
        
        SystemLog.objects.create(
            table_name="Customer",
            record_id=str(instance.id),
            action=action_msg,
            changed_by=changed_by_user,
            target_name=instance.full_name,
            old_data="N/A",
            new_data=f"Customer {instance.pppoe_username} ({instance.full_name}) was added to the system.",
        )
    # Log Updates
    elif hasattr(instance, "_original_state") and instance._original_state:
        changes = []
        new_state = {
            "Full Name": instance.full_name,
            "Email": instance.email,
            "Phone": instance.phone,
            "Status": instance.status,
            "Plan": instance.plan.name if instance.plan else "None",
            "Account Type": instance.account_type.type_name if instance.account_type else "None",
            "Barangay": instance.barangay.name if instance.barangay else "None",
            "Agent": instance.agent.name if instance.agent else "None",
            "Router": instance.mikrotik_device.device_name if instance.mikrotik_device else "None",
            "Username": instance.pppoe_username,
            "Password": instance.pppoe_password,
            "Expiration": instance.expires_at.strftime("%Y-%m-%d %H:%M") if instance.expires_at else "None",
        }

        for field, old_val in instance._original_state.items():
            new_val = new_state.get(field)
            if str(old_val) != str(new_val):
                changes.append(f"{field}: '{old_val}' \u2192 '{new_val}'")

        if changes:
            log_action = "Profile Update"
            if len(changes) == 1:
                field_name = changes[0].split(":")[0].strip()
                log_action = f"Change {field_name}"
            elif len(changes) == 2:
                f1 = changes[0].split(":")[0].strip()
                f2 = changes[1].split(":")[0].strip()
                log_action = f"Change {f1} & {f2}"

            SystemLog.objects.create(
                table_name="Customer",
                record_id=str(instance.id),
                action=log_action,
                changed_by=changed_by_user,
                target_name=instance.full_name,
                old_data="\n".join(changes),
                new_data="Profile updated via UI or API",
            )


@receiver(post_save, sender=Customer)
def notify_customer_status_change(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    """
    Creates a high-priority system notification when a customer is suspended or expired.
    """
    if (
        not created
        and hasattr(instance, "_original_state")
        and instance._original_state
    ):
        old_status = instance._original_state.get("Status")
        new_status = instance.status

        if old_status != new_status and new_status in ["suspended", "expired"]:
            from billing.models import Notification
            from django.urls import reverse

            try:
                customer_url = reverse("view_customer", args=[instance.id])
                Notification.objects.create(
                    title=f"Customer {new_status.title()}",
                    message=f"{instance.full_name}'s account has been marked as {new_status}.",
                    notification_type="network",  # network type triggers high-priority UI
                    link=customer_url,
                )
            except Exception as e:
                logger.error(
                    f"Failed to create status notification for {instance.full_name}: {e}"
                )


@receiver(post_delete, sender=Customer)
def delete_customer_from_mikrotik(sender, instance, **kwargs):
    """
    When a Customer is deleted in Django, remove their PPP secret and any bridge drop rules from their Mikrotik device.
    """
    if getattr(instance, "is_test_data", False) or not instance.mikrotik_device or not instance.pppoe_username:
        return

    try:
        api = MikrotikAPI(instance.mikrotik_device)
        api.delete_pppoe_user(instance.pppoe_username)
    except Exception as e:
        logger.error(
            f"Error deleting customer {instance.pppoe_username} from Mikrotik: {e}"
        )


from .models import SubscriptionPlan
from network_manager.models import MikrotikDevice


@receiver(post_save, sender=SubscriptionPlan)
def sync_plan_on_save(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    """
    Push a plan's bandwidth profile to every active MikroTik device.

    Two things this used to get wrong, both of which mattered after the legacy
    import:

    1. It synced `instance.name`. The display name is not the router's profile
       name -- `router_profile` exists precisely because they differ (staff see
       "GTipid Fiber 1000", the router knows "pppoe-20m"). Syncing the display
       name invented profiles the routers never had.

    2. On rename it deleted the old profile unconditionally. Renaming a plan
       whose old name was a live profile therefore stripped the rate limits
       from every subscriber on it -- and it only stayed harmless because the
       routers happened to be unreachable. Same loaded gun the post_delete
       handler already guards against, so it uses the same guard here.

    The profile actually written is `effective_router_profile`, the same value
    the Sync Manager compares against, so a plan cannot be synced to a router
    under one name and verified under another.
    """
    profile = (getattr(instance, "router_profile", "") or instance.name or "").strip()

    devices = MikrotikDevice.objects.all()

    # Rename: only remove the profile the plan used to occupy, and only when
    # nothing depends on it any more.
    old_name = getattr(instance, "_original_name", None)
    if old_name and old_name != instance.name:
        old_profile = old_name.strip()
        in_use = Customer.objects.filter(
            plan__router_profile=old_profile
        ).exclude(plan__isnull=True).distinct().count()
        sibling = SubscriptionPlan.objects.filter(
            router_profile=old_profile
        ).exclude(pk=instance.pk).count()

        if in_use or sibling:
            logger.warning(
                "KEPT router profile '%s' on rename: %d subscriber(s) and %d "
                "sibling plan(s) still use it. The display name changed; the "
                "router profile was left alone.",
                old_profile, in_use, sibling,
            )
        else:
            for device in devices:
                try:
                    MikrotikAPI(device).delete_plan_from_mikrotik(plan_name=old_profile)
                except Exception as e:
                    logger.warning(
                        "Could not delete old profile %s from %s during rename: %s",
                        old_profile, device.device_name, e,
                    )

    for device in devices:
        try:
            MikrotikAPI(device).sync_plan_to_mikrotik(
                plan_name=profile,
                speed_up=instance.speed_up,
                speed_down=instance.speed_down,
            )
        except Exception as e:
            logger.error(
                f"Failed to sync plan {instance.name} to {device.device_name}: {e}"
            )


from django.db.models.signals import post_delete


@receiver(post_delete, sender=SubscriptionPlan)
def delete_plan_on_mikrotik(sender, instance, **kwargs):
    """
    When a SubscriptionPlan is deleted in Django, remove it from all active Mikrotik devices.

    GUARD: never touch a router profile that a live subscriber is still on.

    This signal used to fire unconditionally, which is a loaded gun. Deleting a
    plan row whose name matches a real router profile removed that profile from
    EVERY router -- so tidying up a duplicate plan in the admin would silently
    strip the rate limits of every customer on that profile. It was only ever
    "safe" because the routers happened to be powered off.

    A profile is only removed when no customer points at any plan that maps to it.
    Otherwise we log loudly and leave the router alone: an unused stale profile
    is a cosmetic problem, a deleted one is an outage.
    """
    profile = (getattr(instance, "router_profile", "") or instance.name or "").strip()

    in_use = Customer.objects.filter(
        plan__router_profile=profile
    ).exclude(plan__isnull=True).distinct().count()
    # A plan that still maps to the same profile also protects it.
    sibling = SubscriptionPlan.objects.filter(
        router_profile=profile
    ).exclude(pk=instance.pk).count()

    if in_use or sibling:
        logger.warning(
            "KEPT router profile '%s': %d subscriber(s) and %d sibling plan(s) "
            "still use it. Deleting the Django row does not touch the router.",
            profile, in_use, sibling,
        )
        return

    for device in MikrotikDevice.objects.all():
        try:
            api = MikrotikAPI(device)
            api.delete_plan_from_mikrotik(plan_name=profile)
        except Exception as e:
            logger.error(
                f"Failed to delete plan {profile} from {device.device_name}: {e}"
            )


from django.contrib.auth.models import User
from .models import EmployeeProfile


@receiver(post_save, sender=User)
def create_employee_profile(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
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
    if hasattr(instance, "employee_profile"):
        instance.employee_profile.save()


from django.contrib.auth.signals import user_logged_in


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Keep a historical record of when admins log in.
    """
    from billing.models import SystemLog

    # Get IP if possible
    ip_addr = "Unknown"
    if request:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_addr = x_forwarded_for.split(",")[0]
        else:
            ip_addr = request.META.get("REMOTE_ADDR", "Unknown")

    SystemLog.objects.create(
        table_name="User",
        record_id=str(user.id),
        action="LOGIN",
        changed_by=user.username,
        target_name=user.username,
        old_data=f"IP: {ip_addr}",
        new_data="User successfully logged in.",
    )


from billing.models import Payment


@receiver(post_save, sender=Payment)
def payment_post_save_incentive_trigger(sender, instance, created, **kwargs):
    """
    Triggers the Agent Incentive Engine whenever a payment is created or updated.
    Evaluates 2nd-month qualification, advance payments, and rollback adjustments.
    """
    from django.conf import settings
    if not getattr(settings, "INCENTIVES_ENABLED", False) or kwargs.get("raw"):
        return
    customer = instance.customer
    if not customer and instance.username:
        customer = Customer.objects.filter(pppoe_username=instance.username).first()
    if not customer:
        return
    try:
        from billing.services.incentives import evaluate_agent_qualification
        evaluate_agent_qualification(customer, triggering_payment=instance)
    except Exception as e:
        logger.warning(f"Incentive qualification evaluation failed on Payment {instance.id}: {e}")


@receiver(post_delete, sender=Payment)
def payment_post_delete_incentive_trigger(sender, instance, **kwargs):
    """
    Re-evaluates agent qualification if a payment is deleted.
    """
    from django.conf import settings
    if not getattr(settings, "INCENTIVES_ENABLED", False):
        return
    customer = instance.customer
    if not customer and instance.username:
        customer = Customer.objects.filter(pppoe_username=instance.username).first()
    if not customer:
        return
    try:
        from billing.services.incentives import evaluate_agent_qualification
        evaluate_agent_qualification(customer)
    except Exception as e:
        logger.warning(f"Incentive qualification evaluation failed on Payment delete {instance.id}: {e}")

