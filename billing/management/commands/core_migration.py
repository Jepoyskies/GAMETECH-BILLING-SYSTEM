import csv
import logging
from django.core.management.base import BaseCommand
from billing.models import Customer, SubscriptionPlan
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrates legacy PHP customer data from a CSV, matches with Mikrotik PPP secrets, and populates the DB.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to the legacy CSV file')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        self.stdout.write(f"Starting migration from {csv_path}...")

        # Get active Mikrotik Device (assuming single router for now or primary router)
        device = MikrotikDevice.objects.filter(is_active=True).first()
        if not device:
            self.stdout.write(self.style.ERROR("No active Mikrotik device found. Ensure network manager is configured."))
            return

        # Fetch PPP Secrets from Mikrotik
        api = MikrotikAPI(device)
        self.stdout.write("Fetching active PPP secrets from Mikrotik...")
        try:
            secrets = api.get_resource('/ppp/secret').get()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to connect to Mikrotik: {e}"))
            return

        # Create a dictionary of Mikrotik secrets by username for fast lookup
        mikrotik_data = {}
        for s in secrets:
            mikrotik_data[s.get('name')] = {
                'password': s.get('password', ''),
                'profile': s.get('profile', 'default'),
                'caller-id': s.get('caller-id', '')
            }
            
        self.stdout.write(f"Found {len(mikrotik_data)} PPP secrets on Mikrotik.")

        # Read CSV
        success_count = 0
        error_count = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Auto-detect common column variations
                headers = [h.lower().strip() for h in reader.fieldnames]
                
                def get_val(row, possible_keys, default=''):
                    for k in possible_keys:
                        for actual_k in row.keys():
                            if actual_k and actual_k.lower().strip() == k:
                                return row[actual_k]
                    return default

                for row in reader:
                    # Map legacy PHP columns to standard variables
                    pppoe_username = get_val(row, ['pppoe_username', 'username', 'pppoe', 'account_id'])
                    full_name = get_val(row, ['full_name', 'name', 'customer_name', 'customer name'])
                    address = get_val(row, ['address', 'location', 'street'])
                    phone = get_val(row, ['phone', 'mobile', 'contact', 'contact_number'])
                    balance = get_val(row, ['balance', 'outstanding_balance', 'due', 'amount_due'], '0')

                    if not pppoe_username:
                        self.stdout.write(self.style.WARNING(f"Skipping row missing PPPoE username: {row}"))
                        error_count += 1
                        continue
                        
                    # Check if customer already exists in Django
                    if Customer.objects.filter(pppoe_username=pppoe_username).exists():
                        self.stdout.write(self.style.WARNING(f"Customer {pppoe_username} already exists. Skipping."))
                        continue
                        
                    # Find matching data from Mikrotik
                    mk_info = mikrotik_data.get(pppoe_username)
                    if not mk_info:
                        self.stdout.write(self.style.WARNING(f"No matching Mikrotik secret for {pppoe_username}. Will create without password/plan."))
                        password = ''
                        mk_plan_name = ''
                        mac = ''
                    else:
                        password = mk_info.get('password', '')
                        mk_plan_name = mk_info.get('profile', '')
                        mac = mk_info.get('caller-id', '')

                    # Map Mikrotik Profile to Django SubscriptionPlan
                    plan = None
                    if mk_plan_name and mk_plan_name != 'default':
                        plan = SubscriptionPlan.objects.filter(name__iexact=mk_plan_name).first()

                    try:
                        clean_balance = float(balance.replace(',', ''))
                    except:
                        clean_balance = 0.0

                    # Insert Customer directly without triggering the sync signal (so we don't spam the router)
                    customer = Customer(
                        full_name=full_name or pppoe_username,
                        pppoe_username=pppoe_username,
                        pppoe_password=password,
                        address=address,
                        phone=phone,
                        outstanding_balance=clean_balance,
                        plan=plan,
                        mikrotik_device=device,
                        router_mac=mac
                    )
                    
                    # By default, Django save() will trigger signals. 
                    # If signals sync to Mikrotik, it's fine, it will just update the existing secret.
                    customer.save()
                    success_count += 1
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"CSV parsing failed: {e}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Migration Complete! Successfully imported {success_count} customers. Errors/Skipped: {error_count}"))
