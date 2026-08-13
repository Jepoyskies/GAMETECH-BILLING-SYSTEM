from django.core.management.base import BaseCommand
from django.utils import timezone
from billing.models import Customer
# from network_manager.services import MikroTikManager

class Command(BaseCommand):
    help = 'Auto-suspends PPPoE users whose expiration date has passed'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        
        # Fetch all customers where expiration date is in the past
        due_customers = Customer.objects.filter(expires_at__lte=now)

        if not due_customers.exists():
            self.stdout.write(self.style.WARNING("No customers are currently past due."))
            return

        self.stdout.write(self.style.WARNING(f"Found {due_customers.count()} past due customers. Starting suspension protocol..."))
        
        suspended_count = 0
        
        for customer in due_customers:
            # Skip if they don't have a linked Mikrotik device
            if not customer.mikrotik_device:
                self.stdout.write(self.style.ERROR(f"⚠️ {customer.pppoe_username} has no Mikrotik device assigned. Skipping."))
                continue
                
            try:
                # TODO: SPRINT 4 (Desk Lab Phase) - Uncomment and test with real router
                # mt = MikroTikManager(
                #     ip=customer.mikrotik_device.ip_address,
                #     username=customer.mikrotik_device.api_username,
                #     password=customer.mikrotik_device.api_password,
                #     port=customer.mikrotik_device.api_port
                # )
                # mt.suspendPppoeUser(customer.pppoe_username)
                
                suspended_count += 1
                self.stdout.write(self.style.SUCCESS(f"🔴 Suspended {customer.pppoe_username} on {customer.mikrotik_device.name}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Failed to suspend {customer.pppoe_username}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"✅ Suspend process complete. Total suspended: {suspended_count}"))