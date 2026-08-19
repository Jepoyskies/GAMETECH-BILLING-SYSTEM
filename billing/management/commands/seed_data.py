from django.core.management.base import BaseCommand
from billing.models import AccountType, Agent, Barangay

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

        self.stdout.write(self.style.SUCCESS('\nSuccessfully seeded default system data!'))
