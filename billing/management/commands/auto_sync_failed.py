from django.core.management.base import BaseCommand
from billing.models import Customer
from network_manager.services import MikrotikAPI
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Automatically retries syncing customers whose sync_status is Failed"

    def handle(self, *args, **kwargs):
        # Fetch all customers with failed sync
        failed_customers = Customer.objects.filter(sync_status="Failed")

        if not failed_customers.exists():
            self.stdout.write(self.style.SUCCESS("No failed syncs found."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {failed_customers.count()} customers with failed sync. Attempting to resync..."
            )
        )

        synced_count = 0

        for customer in failed_customers:
            if not customer.mikrotik_device:
                self.stdout.write(
                    self.style.ERROR(
                        f"[WARNING] {customer.full_name} has no Mikrotik device assigned. Skipping."
                    )
                )
                continue

            try:
                # Retry by re-staging, NOT by writing to the router.
                #
                # This used to call customer.save() and let the post_save signal
                # push the secret, meaning a customer the router rejected once
                # would be re-pushed every 5 minutes forever by a cron job.
                # Router writes are now deliberate: this only makes sure the
                # row is visible in the Sync Manager queue for a human.
                customer.push_to_router = False
                customer.save(update_fields=["sync_status"])
                customer.sync_status = "Pending"
                customer.save(update_fields=["sync_status"])

                synced_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[QUEUED] {customer.full_name} needs a manual push to "
                        f"{customer.mikrotik_device.device_name}. Not written to the router."
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[ERROR] Unexpected error syncing {customer.full_name}: {str(e)}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"[DONE] Auto-sync process complete. Total synced: {synced_count} out of {failed_customers.count()}"
            )
        )
