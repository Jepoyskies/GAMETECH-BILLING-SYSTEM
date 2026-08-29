from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from billing.models import Customer, SystemLog, Payment
from network_manager.services import MikrotikAPI

class Command(BaseCommand):
    help = 'Auto-suspends PPPoE users whose expiration date has passed, or auto-renews them if they have Advance Payment'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        
        # Fetch all customers where expiration date is in the past and status is active
        due_customers = Customer.objects.filter(expires_at__lte=now, status='active')

        if not due_customers.exists():
            self.stdout.write(self.style.WARNING("No active customers are currently past due."))
            return

        self.stdout.write(self.style.WARNING(f"Found {due_customers.count()} active past due customers. Starting check..."))
        
        suspended_count = 0
        renewed_count = 0
        
        for customer in due_customers:
            plan_price = customer.plan.price if customer.plan else 0
            
            # 1. Check if they have enough Advance Payment (outstanding_balance) to auto-renew
            if plan_price > 0 and customer.outstanding_balance >= plan_price:
                # --- AUTO RENEW ---
                from billing.views import calculate_new_expiration_date
                new_expiry = calculate_new_expiration_date(customer.expires_at, float(plan_price), float(plan_price))
                
                customer.expires_at = new_expiry
                customer.outstanding_balance -= plan_price
                customer.save()
                
                # Log the auto-renewal payment record
                Payment.objects.create(
                    customer=customer,
                    username=customer.pppoe_username,
                    plan_name=customer.plan.name if customer.plan else None,
                    amount=plan_price,
                    payment_method='advance_payment',
                    reference_no='AUTO-RENEW',
                    reason='Auto-renewed from Advance Payment wallet',
                    expires_at=new_expiry,
                    adjusted_by='System'
                )
                
                SystemLog.objects.create(
                    table_name='Customer',
                    record_id=str(customer.id),
                    action='UPDATE',
                    changed_by='System (Auto-Renew)',
                    target_name=customer.full_name,
                    old_data=f"expires_at: {customer.expires_at}",
                    new_data=f"Auto-renewed using Advance Payment. New expires_at: {new_expiry}"
                )
                
                renewed_count += 1
                self.stdout.write(self.style.SUCCESS(f"[AUTO-RENEW] {customer.pppoe_username} auto-renewed for 1 month using Advance Payment."))
                continue

            # 2. Otherwise, suspend normally
            # Skip if they don't have a linked Mikrotik device
            if not customer.mikrotik_device:
                self.stdout.write(self.style.ERROR(f"[WARNING] {customer.pppoe_username} has no Mikrotik device assigned. Skipping."))
                continue
                
            try:
                # Initialize the new MikrotikAPI utility
                mt = MikrotikAPI(customer.mikrotik_device)
                
                # Suspend the user (handles MAC-level drop, secret disable, and active session kick)
                success, message = mt.suspend_pppoe_user(customer.pppoe_username)
                
                if success:
                    # Update customer status in the DB
                    customer.status = 'suspended'
                    customer.save()
                    
                    # Create an audit log entry
                    SystemLog.objects.create(
                        table_name='Customer',
                        record_id=str(customer.id),
                        action='UPDATE',
                        changed_by='System (Auto-Suspend)',
                        target_name=customer.full_name,
                        old_data='status: active',
                        new_data='status: suspended'
                    )
                    
                    suspended_count += 1
                    self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Suspended {customer.pppoe_username} on {customer.mikrotik_device.device_name}: {message}"))
                else:
                    self.stdout.write(self.style.ERROR(f"[FAILED] Failed to suspend {customer.pppoe_username} on Mikrotik: {message}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[ERROR] Unexpected error suspending {customer.pppoe_username}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"[DONE] Process complete. Suspended: {suspended_count} | Auto-Renewed: {renewed_count}"))