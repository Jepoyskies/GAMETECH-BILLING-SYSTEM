from django.core.management.base import BaseCommand
from billing.models import AccountType, Agent, Barangay, SubscriptionPlan

class Command(BaseCommand):
    help = 'Seeds the database with default Account Types, Agents, and Barangays.'

    def handle(self, *args, **kwargs):
        # 1. Seed Account Types
        account_types = ['Residential', 'Commercial', 'VIP', 'Government']
        for at_name in account_types:
            obj, created = AccountType.objects.get_or_create(type_name=at_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Account Type: {at_name}"))
            else:
                self.stdout.write(f"Account Type already exists: {at_name}")

        # 2. Seed Agents
        agents = [
            {'name': 'Walk-in / Direct', 'email': 'walkin@example.com', 'phone': '00000000000'},
            {'name': 'Agent John Doe', 'email': 'john@example.com', 'phone': '09123456789'},
            {'name': 'Agent Jane Smith', 'email': 'jane@example.com', 'phone': '09987654321'},
        ]
        for agent_data in agents:
            obj, created = Agent.objects.get_or_create(
                name=agent_data['name'],
                defaults={'email': agent_data['email'], 'phone': agent_data['phone']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Agent: {agent_data['name']}"))
            else:
                self.stdout.write(f"Agent already exists: {agent_data['name']}")

        # 3. Seed Barangays
        barangays = [
            'Barangay 1',
            'Barangay 2',
            'Barangay 3',
            'Poblacion',
            'San Jose',
            'San Isidro'
        ]
        for brgy_name in barangays:
            obj, created = Barangay.objects.get_or_create(name=brgy_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Barangay: {brgy_name}"))
            else:
                self.stdout.write(f"Barangay already exists: {brgy_name}")

        # 4. Seed Subscription Plans
        plans = [
            {'name': '5Mbps', 'speed_up': '5 Mbps', 'speed_down': '5 Mbps', 'price': 500.00},
            {'name': '10Mbps', 'speed_up': '10 Mbps', 'speed_down': '10 Mbps', 'price': 750.00},
            {'name': '20Mbps', 'speed_up': '20 Mbps', 'speed_down': '20 Mbps', 'price': 1000.00},
            {'name': '30Mbps', 'speed_up': '30 Mbps', 'speed_down': '30 Mbps', 'price': 1250.00},
            {'name': '50Mbps', 'speed_up': '50 Mbps', 'speed_down': '50 Mbps', 'price': 1500.00},
        ]
        
        for plan_data in plans:
            obj, created = SubscriptionPlan.objects.get_or_create(
                name=plan_data['name'],
                defaults={
                    'speed_up': plan_data['speed_up'],
                    'speed_down': plan_data['speed_down'],
                    'price': plan_data['price'],
                    'validity_days': 30
                }
            )
            # Ensure price is updated if the plan already exists but was 0.00
            if not created and obj.price == 0.00:
                obj.price = plan_data['price']
                obj.save()
                self.stdout.write(self.style.SUCCESS(f"Updated Plan Price: {plan_data['name']} to {plan_data['price']}"))
            elif created:
                self.stdout.write(self.style.SUCCESS(f"Created Plan: {plan_data['name']}"))
            else:
                self.stdout.write(f"Plan already exists: {plan_data['name']}")

        self.stdout.write(self.style.SUCCESS('\nSuccessfully seeded default system data!'))
