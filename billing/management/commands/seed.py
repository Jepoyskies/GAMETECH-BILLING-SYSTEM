import random
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from billing.models import AccountType, Agent, SubscriptionPlan, Barangay, Customer, Payment, AddOnRequest, SystemLog
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
            SystemLog.objects.all().delete()
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
import random
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from billing.models import AccountType, Agent, SubscriptionPlan, Barangay, Customer, Payment, AddOnRequest, SystemLog, SystemAdmin
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
            SystemLog.objects.all().delete()
            SystemAdmin.objects.all().delete()
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

        # 0. Create System Admins (Staff)
        self.stdout.write('Creating Staff & Admins...')
        staff_data = [
            ('MeiMei', 'MeiMei the Icebear', 'Meimeitheicebear@gmail.com', 'Admin', 'Active'),
            ('JillianAthea', 'Jillian Athea', 'jillian@gametech.com', 'Admin', 'Active'),
            ('TechMike', 'Mike Ross', 'mike@gametech.com', 'Technician', 'Active'),
            ('CSRAna', 'Ana Santos', 'ana.csr@gametech.com', 'CSR', 'Active'),
            ('Agent007', 'James Bond', 'james@gametech.com', 'Agent', 'Inactive'),
        ]
        sys_admins = []
        for username, full_name, email, role, status in staff_data:
            user, created = User.objects.get_or_create(username=username, defaults={'email': email})
            if created:
                user.set_password('password123')
                user.save()
            
            admin, _ = SystemAdmin.objects.update_or_create(
                username=username,
                defaults={
                    'full_name': full_name,
                    'email': email,
                    'role': role,
                    'status': status
                }
            )
            sys_admins.append(admin)

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

        # 10. System Logs
        self.stdout.write('Creating System Logs...')
        sys_admin_names = [a.username for a in sys_admins]
        if not sys_admin_names:
            sys_admin_names = ['Admin']
        logs_to_create = []

        for _ in range(3):
            current_admin = random.choice(sys_admin_names)
            # 1. Customer Plan Upgrade
            if Customer.objects.exists() and len(plans) > 1:
                c = Customer.objects.order_by('?').first()
                old_plan = plans[0].name
                new_plan = plans[-1].name
                logs_to_create.append({
                    'table_name': 'Customer',
                    'record_id': str(c.id),
                    'action': 'UPDATE',
                    'changed_by': current_admin,
                    'old_data': f"Plan: '{old_plan}'",
                    'new_data': f"Plan: '{new_plan}'",
                    'days_ago': random.randint(1, 20)
                })

            # 2. Customer Address Update
            if Customer.objects.exists():
                c = Customer.objects.order_by('?').first()
                logs_to_create.append({
                    'table_name': 'Customer',
                    'record_id': str(c.id),
                    'action': 'UPDATE',
                    'changed_by': current_admin,
                    'old_data': f"Address: 'Old Address'",
                    'new_data': f"Address: '{c.address}'",
                    'days_ago': random.randint(1, 20)
                })

            # 3. Add-on Request Resolved
            if AddOnRequest.objects.exists():
                addon = AddOnRequest.objects.order_by('?').first()
                logs_to_create.append({
                    'table_name': 'AddOnRequest',
                    'record_id': str(addon.id),
                    'action': 'UPDATE',
                    'changed_by': current_admin,
                    'old_data': "Status: 'Pending'",
                    'new_data': "Status: 'Resolved'",
                    'days_ago': random.randint(1, 10)
                })

            # 4. Agent Created
            if agents:
                a = random.choice(agents)
                logs_to_create.append({
                    'table_name': 'Agent',
                    'record_id': str(a.id),
                    'action': 'ADD',
                    'changed_by': current_admin,
                    'old_data': None,
                    'new_data': f"Name: '{a.name}', Email: '{a.email}', Phone: '{a.phone}'",
                    'days_ago': random.randint(5, 25)
                })

            # 5. Customer Status Suspended
            if Customer.objects.exists():
                c = Customer.objects.order_by('?').first()
                logs_to_create.append({
                    'table_name': 'Customer',
                    'record_id': str(c.id),
                    'action': 'UPDATE',
                    'changed_by': 'System/AutoSuspend',
                    'old_data': "Status: 'active'",
                    'new_data': "Status: 'suspended'\nReason: 'Overdue Balance'",
                    'days_ago': random.randint(1, 15)
                })

            # 6. Customer Deleted
            logs_to_create.append({
                'table_name': 'Customer',
                'record_id': str(random.randint(9000, 9999)),
                'action': 'DELETE',
                'changed_by': current_admin,
                'old_data': f"Username: 'user{random.randint(100, 999)}'\nStatus: 'suspended'\nPlan: '20 Mbps Plan'",
                'new_data': None,
                'days_ago': random.randint(1, 30)
            })

            # 7. Subscription Plan Price Change
            if plans:
                p = random.choice(plans)
                old_price = float(p.price) - 100
                logs_to_create.append({
                    'table_name': 'SubscriptionPlan',
                    'record_id': str(p.id),
                    'action': 'UPDATE',
                    'changed_by': current_admin,
                    'old_data': f"Price: '{old_price}'",
                    'new_data': f"Price: '{p.price}'",
                    'days_ago': random.randint(10, 30)
                })

            # 8. Payment Voided
            logs_to_create.append({
                'table_name': 'Payment',
                'record_id': str(random.randint(4000, 5000)),
                'action': 'DELETE',
                'changed_by': current_admin,
                'old_data': f"Amount: '{random.choice([999.00, 1499.00, 1999.00])}'\nMethod: '{random.choice(['GCash', 'Cash', 'Bank Transfer'])}'\nReference: '{str(uuid.uuid4())[:8].upper()}'",
                'new_data': None,
                'days_ago': random.randint(1, 20)
            })

            # 9. Mikrotik Device Added
            if MikrotikDevice.objects.exists():
                m = MikrotikDevice.objects.first()
                logs_to_create.append({
                    'table_name': 'MikrotikDevice',
                    'record_id': str(m.id),
                    'action': 'ADD',
                    'changed_by': current_admin,
                    'old_data': None,
                    'new_data': f"Device Name: 'Router-{random.randint(1, 10)}'\nIP: '192.168.1.{random.randint(2, 254)}'",
                    'days_ago': random.randint(20, 30)
                })

            # 10. Customer Reactivated
            if Customer.objects.exists():
                c = Customer.objects.order_by('?').first()
                logs_to_create.append({
                    'table_name': 'Customer',
                    'record_id': str(c.id),
                    'action': 'UPDATE',
                    'changed_by': random.choice(agents).user.username if agents and agents[0].user else current_admin,
                    'old_data': "Status: 'suspended'",
                    'new_data': "Status: 'active'\nBalance Cleared: True",
                    'days_ago': random.randint(1, 15)
                })
            # 11. Staff Created (SystemAdmin)
            if sys_admins:
                s = random.choice(sys_admins)
                logs_to_create.append({
                    'table_name': 'SystemAdmin',
                    'record_id': str(s.id),
                    'action': 'ADD',
                    'changed_by': current_admin,
                    'old_data': None,
                    'new_data': f"Username: '{s.username}', Role: '{s.role}'",
                    'days_ago': random.randint(15, 30)
                })

            # 12. NapBox Added
            if NapBox.objects.exists():
                n = NapBox.objects.order_by('?').first()
                logs_to_create.append({
                    'table_name': 'NapBox',
                    'record_id': str(n.id),
                    'action': 'ADD',
                    'changed_by': current_admin,
                    'old_data': None,
                    'new_data': f"NapBox No: '{n.napbox_no}'",
                    'days_ago': random.randint(5, 25)
                })

            # 13. AccountType Added
            if acc_types:
                a = random.choice(acc_types)
                logs_to_create.append({
                    'table_name': 'AccountType',
                    'record_id': str(a.id),
                    'action': 'ADD',
                    'changed_by': current_admin,
                    'old_data': None,
                    'new_data': f"Name: '{a.type_name}'",
                    'days_ago': random.randint(20, 40)
                })

            # 14. Barangay Added
            if barangays:
                b = random.choice(barangays)
                logs_to_create.append({
                    'table_name': 'Barangay',
                    'record_id': str(b.id),
                    'action': 'ADD',
                    'changed_by': current_admin,
                    'old_data': None,
                    'new_data': f"Name: '{b.name}'",
                    'days_ago': random.randint(15, 35)
                })

            # 15. Payment Added
            if Payment.objects.exists():
                pay = Payment.objects.order_by('?').first()
                logs_to_create.append({
                    'table_name': 'Payment',
                    'record_id': str(pay.id),
                    'action': 'ADD',
                    'changed_by': current_admin,
                    'old_data': None,
                    'new_data': f"Amount: '{pay.amount}'\nMethod: '{pay.payment_method}'",
                    'days_ago': random.randint(1, 10)
                })

            # 16. Mikrotik Device Updated
            if MikrotikDevice.objects.exists():
                m = MikrotikDevice.objects.first()
                logs_to_create.append({
                    'table_name': 'MikrotikDevice',
                    'record_id': str(m.id),
                    'action': 'UPDATE',
                    'changed_by': current_admin,
                    'old_data': f"IP: '192.168.0.1'",
                    'new_data': f"IP: '192.168.1.1'",
                    'days_ago': random.randint(5, 15)
                })

            # 17. Subscription Plan Created
            if plans:
                p = random.choice(plans)
                logs_to_create.append({
                    'table_name': 'SubscriptionPlan',
                    'record_id': str(p.id),
                    'action': 'ADD',
                    'changed_by': current_admin,
                    'old_data': None,
                    'new_data': f"Name: '{p.name}', Speed: '{p.speed_down}'",
                    'days_ago': random.randint(25, 45)
                })

        for log_data in logs_to_create:
            log_obj = SystemLog.objects.create(
                table_name=log_data['table_name'],
                record_id=log_data['record_id'],
                action=log_data['action'],
                changed_by=log_data['changed_by'],
                old_data=log_data['old_data'],
                new_data=log_data['new_data']
            )
            past_date = timezone.now() - timedelta(days=log_data['days_ago'], hours=random.randint(1, 23), minutes=random.randint(1, 59))
            SystemLog.objects.filter(id=log_obj.id).update(changed_at=past_date)

        self.stdout.write(self.style.SUCCESS('Successfully seeded the database!'))
