import random
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from billing.models import AccountType, Agent, SubscriptionPlan, Barangay, Customer, Payment, AddOnRequest
from network_manager.models import MikrotikDevice, NapBox

class Command(BaseCommand):
    help = 'Seed the database with realistic test data'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear existing data before seeding')

    def handle(self, *args, **kwargs):
        from django.db.models.signals import post_save, post_delete
        from billing.signals import (
            sync_customer_to_mikrotik, 
            delete_customer_from_mikrotik, 
            sync_plan_on_save, 
            delete_plan_on_mikrotik
        )
        
        # Disconnect signals to prevent Mikrotik API timeouts during seeding
        post_save.disconnect(sync_customer_to_mikrotik, sender=Customer)
        post_delete.disconnect(delete_customer_from_mikrotik, sender=Customer)
        post_save.disconnect(sync_plan_on_save, sender=SubscriptionPlan)
        post_delete.disconnect(delete_plan_on_mikrotik, sender=SubscriptionPlan)

        if kwargs['clear']:
            self.stdout.write('Clearing existing data...')
            Payment.objects.all().delete()
            Customer.objects.all().delete()
            NapBox.objects.all().delete()
            MikrotikDevice.objects.all().delete()
            Barangay.objects.all().delete()
            SubscriptionPlan.objects.all().delete()
            AccountType.objects.all().delete()
            Agent.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write('Data cleared.')

        self.stdout.write('Seeding data...')

        # 1. Create Users & Agents
        self.stdout.write('Creating Agents...')
        agents = []
        agents_data = [
            ('qwertyui', 'qwertyui', 'asdfgh@gmail.com', '12345678'),
            ('MeiMei', 'MeiMei the Icebear', 'Meimeitheicebear@gmail.com', '09123456789')
        ]
        for username, name, email, phone in agents_data:
            user, created = User.objects.get_or_create(username=username, defaults={'email': email})
            if created:
                user.set_password('password123')
                user.save()
            agent, _ = Agent.objects.update_or_create(
                email=email, 
                defaults={
                    'user': user,
                    'name': name,
                    'phone': phone
                }
            )
            agents.append(agent)

        # 2. Account Types
        self.stdout.write('Creating Account Types...')
        acc_types = []
        for type_name in ['Residential', 'Business', 'VIP']:
            acc_type, _ = AccountType.objects.get_or_create(type_name=type_name)
            acc_types.append(acc_type)

        # 3. Subscription Plans
        self.stdout.write('Creating Subscription Plans...')
        plans = []
        plan_data = [
            ('20 Mbps Plan', '20M', '20M', 999.00),
            ('30 Mbps Plan', '30M', '30M', 1299.00),
            ('50 Mbps Plan', '50M', '50M', 1499.00),
            ('75 Mbps Plan', '75M', '75M', 1999.00),
            ('100 Mbps Plan', '100M', '100M', 2499.00),
        ]
        for name, up, down, price in plan_data:
            plan, _ = SubscriptionPlan.objects.get_or_create(
                name=name, 
                defaults={'speed_up': up, 'speed_down': down, 'price': price, 'validity_days': 30}
            )
            plans.append(plan)

        # 4. Barangays
        self.stdout.write('Creating Barangays...')
        barangays = []
        for b_name in ['lumbia', 'carmen', 'macasandig', 'balulang']:
            barangay, _ = Barangay.objects.get_or_create(name=b_name, defaults={'health_status': 'Excellent'})
            barangays.append(barangay)

        # 5. Mikrotik Devices
        self.stdout.write('Creating Mikrotik Devices...')
        mikrotik, _ = MikrotikDevice.objects.get_or_create(
            device_name='Main Router - Gametech',
            defaults={
                'ip_address': '192.168.1.1',
                'api_username': 'admin',
                'api_password': 'password',
            }
        )
        
        # 6. Nap Boxes
        self.stdout.write('Creating Nap Boxes...')
        for i in range(1, 6):
            NapBox.objects.get_or_create(napbox_no=f'NAP-0{i}')

        # 7. Customers
        self.stdout.write('Creating Customers...')
        first_names = ['Juan', 'Maria', 'Pedro', 'Ana', 'Jose', 'Luz', 'Carlos', 'Elena', 'Mark', 'Teresa', 'Antonio', 'Rosa']
        last_names = ['Dela Cruz', 'Santos', 'Reyes', 'Cruz', 'Bautista', 'Ocampo', 'Garcia', 'Mendoza', 'Torres', 'Tomas']
        
        # Add the specific customer from the datadump
        customer, created = Customer.objects.update_or_create(
            email='fyuytuyt@gmail.com',
            defaults={
                'pppoe_username': 'fyuytuyt',
                'full_name': 'fyuytuyt',
                'phone': '09123456789',
                'address': 'portico subd.',
                'plan': plans[0],
                'agent': agents[0],
                'barangay': barangays[0],
                'account_type': acc_types[0],
                'mikrotik_device': mikrotik,
                'status': 'pending',
                'health_status': 'Good'
            }
        )
        
        for i in range(1, 26):
            first = random.choice(first_names)
            last = random.choice(last_names)
            full_name = f"{first} {last}"
            username = f"{first.lower()}.{last.lower().replace(' ', '')}{i}"
            
            customer, created = Customer.objects.get_or_create(
                pppoe_username=username,
                defaults={
                    'full_name': full_name,
                    'email': f"{username}@example.com",
                    'phone': f"09{random.randint(100000000, 999999999)}",
                    'address': f"Block {random.randint(1, 20)} Lot {random.randint(1, 50)}, {random.choice(barangays).name}",
                    'plan': random.choice(plans),
                    'agent': random.choice(agents),
                    'barangay': random.choice(barangays),
                    'account_type': random.choice(acc_types),
                    'mikrotik_device': mikrotik,
                    'status': random.choice(['active', 'active', 'active', 'suspended', 'pending']),
                    'health_status': random.choice(['Good', 'Stable', 'Excellent', 'Low', 'Offline']),
                    'outstanding_balance': random.choice([0.00, 0.00, 500.00, 1499.00, -200.00]),
                    'pppoe_password': 'password123',
                    'mac_address': f"00:1A:2B:3C:4D:{random.randint(10,99)}",
                    'expires_at': timezone.now() + timedelta(days=random.randint(-5, 25))
                }
            )
            
            # 8. Add dummy payments
            if created and customer.status == 'active':
                Payment.objects.create(
                    customer=customer,
                    username=customer.pppoe_username,
                    plan_name=customer.plan.name,
                    amount=customer.plan.price,
                    payment_method=random.choice(['Cash', 'GCash', 'Bank Transfer']),
                    reference_no=str(uuid.uuid4())[:8].upper(),
                    paid_at=timezone.now() - timedelta(days=random.randint(1, 30))
                )

            # 9. Add dummy Add-on requests
            if random.choice([True, False, False]):
                AddOnRequest.objects.create(
                    customer=customer,
                    addon_type=random.choice(['Static IP', 'Cignal Play Premium', 'Mesh Router', 'Cable Extension']),
                    status=random.choice(['Pending', 'Pending', 'Resolved'])
                )

        self.stdout.write(self.style.SUCCESS('Successfully seeded the database!'))
