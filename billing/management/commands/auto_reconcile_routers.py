from django.core.management.base import BaseCommand
from billing.models import Customer
from network_manager.models import MikrotikDevice
from network_manager.sync_services import MikrotikAPI
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Automatically reconciles Mikrotik routers with the Django database source of truth.'

    def handle(self, *args, **kwargs):
        devices = MikrotikDevice.objects.all()
        
        if not devices.exists():
            self.stdout.write(self.style.WARNING("No routers found. Skipping reconciliation."))
            return

        for device in devices:
            self.stdout.write(self.style.SUCCESS(f"\n--- Reconciling Router: {device.device_name} ({device.ip_address}) ---"))
            
            try:
                api = MikrotikAPI(
                    ip_address=device.ip_address,
                    username=device.api_username,
                    password=device.api_password,
                    port=device.api_port
                )
                
                # Fetch all users currently on the router
                result = api.get_all_pppoe_users()
                if not result.get('success'):
                    self.stdout.write(self.style.ERROR(f"Failed to connect: {result.get('error')}"))
                    continue
                    
                router_users = result.get('data', [])
                router_dict = {u.get('name'): u for u in router_users if u.get('name')}
                
                # Fetch all Django customers assigned to this router
                django_customers = Customer.objects.filter(mikrotik_device=device).exclude(status='pull out')
                
                pushed_count = 0
                updated_count = 0
                
                for customer in django_customers:
                    uname = customer.pppoe_username
                    target_profile = customer.plan.name if customer.plan else "default"
                    
                    # Construct safe comment
                    secret_comment = customer.generate_mikrotik_comment()
                    
                    if uname not in router_dict:
                        # MISSING ON ROUTER -> PUSH
                        res = api.add_pppoe_user(
                            name=uname,
                            password=customer.pppoe_password,
                            profile=target_profile,
                            comment=secret_comment
                        )
                        if res.get('success'):
                            pushed_count += 1
                            self.stdout.write(f"[PUSHED] Missing user created: {uname}")
                            if customer.sync_status == 'Failed':
                                customer.sync_status = 'Synced'
                                customer.save(update_fields=['sync_status'])
                        else:
                            self.stdout.write(self.style.ERROR(f"[ERROR] Failed to push {uname}: {res.get('error')}"))
                    else:
                        # EXISTS ON ROUTER -> VERIFY SYNC
                        r_user = router_dict[uname]
                        needs_update = False
                        
                        if r_user.get('password') != customer.pppoe_password:
                            needs_update = True
                        if r_user.get('profile') != target_profile:
                            needs_update = True
                            
                        # Notice we don't strictly enforce comment match to prevent endless minor diff updates,
                        # but if profile or password changes, we push the full update.
                        
                        if needs_update:
                            res = api.add_pppoe_user(
                                name=uname,
                                password=customer.pppoe_password,
                                profile=target_profile,
                                comment=secret_comment
                            )
                            if res.get('success'):
                                updated_count += 1
                                self.stdout.write(self.style.SUCCESS(f"[UPDATED] Fixed drift for user: {uname}"))
                                if customer.sync_status == 'Failed':
                                    customer.sync_status = 'Synced'
                                    customer.save(update_fields=['sync_status'])
                            else:
                                self.stdout.write(self.style.ERROR(f"[ERROR] Failed to update {uname}: {res.get('error')}"))
                        else:
                            # Already in sync, clear Failed status if any
                            if customer.sync_status == 'Failed':
                                customer.sync_status = 'Synced'
                                customer.save(update_fields=['sync_status'])
                                
                self.stdout.write(self.style.SUCCESS(f"Finished {device.device_name}: {pushed_count} pushed, {updated_count} updated."))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Unexpected error reconciling {device.device_name}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS("\nAuto-Reconciliation Complete!"))
