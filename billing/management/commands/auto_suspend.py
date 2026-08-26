from django.core.management.base import BaseCommand
from django.utils import timezone
from billing.models import Customer, SystemLog
from network_manager.services import MikrotikAPI

class Command(BaseCommand):
    help = 'Auto-suspends PPPoE users whose expiration date has passed'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        
        # Fetch all customers where expiration date is in the past and status is active
        due_customers = Customer.objects.filter(expires_at__lte=now, status='active')

        if not due_customers.exists():
            self.stdout.write(self.style.WARNING("No active customers are currently past due."))
            return

        self.stdout.write(self.style.WARNING(f"Found {due_customers.count()} active past due customers. Starting suspension protocol..."))
        
        suspended_count = 0
        
        for customer in due_customers:
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

        self.stdout.write(self.style.SUCCESS(f"[DONE] Suspend process complete. Total suspended: {suspended_count}"))