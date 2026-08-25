from django.core.management.base import BaseCommand
from billing.models import Customer
from network_manager.services import MikrotikAPI
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Automatically retries syncing customers whose sync_status is Failed'

    def handle(self, *args, **kwargs):
        # Fetch all customers with failed sync
        failed_customers = Customer.objects.filter(sync_status='Failed')

        if not failed_customers.exists():
            self.stdout.write(self.style.SUCCESS("No failed syncs found."))
            return

        self.stdout.write(self.style.WARNING(f"Found {failed_customers.count()} customers with failed sync. Attempting to resync..."))
        
        synced_count = 0
        
        for customer in failed_customers:
            if not customer.mikrotik_device:
                self.stdout.write(self.style.ERROR(f"[WARNING] {customer.full_name} has no Mikrotik device assigned. Skipping."))
                continue
                
            try:
                # Triggering save() will fire the post_save signal which contains the robust sync logic
                customer.save()
                
                # Check if it succeeded after the signal runs
                customer.refresh_from_db()
                if customer.sync_status == 'Synced':
                    synced_count += 1
                    self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Successfully synced {customer.full_name} to {customer.mikrotik_device.device_name}."))
                else:
                    self.stdout.write(self.style.ERROR(f"[FAILED] Failed to sync {customer.full_name}. Router might still be offline."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[ERROR] Unexpected error syncing {customer.full_name}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"[DONE] Auto-sync process complete. Total synced: {synced_count} out of {failed_customers.count()}"))
