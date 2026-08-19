from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from billing.models import Customer, Payment
from network_manager.models import MikrotikDevice

class Command(BaseCommand):
    help = 'Sets up default RBAC groups and permissions for Gametech Billing System'

    def handle(self, *args, **kwargs):
        # Create groups
        groups = ['Technician', 'Agent', 'CSR', 'Admin']
        for group_name in groups:
            Group.objects.get_or_create(name=group_name)
            self.stdout.write(self.style.SUCCESS(f'Group "{group_name}" ensured.'))

        # Helper function to get permissions by codename for specific content types
        def get_perms(model, actions):
            ct = ContentType.objects.get_for_model(model)
            model_name = model._meta.model_name
            codenames = [f"{action}_{model_name}" for action in actions]
            return Permission.objects.filter(content_type=ct, codename__in=codenames)

        def assign_perms(group_name, permissions):
            group = Group.objects.get(name=group_name)
            group.permissions.set(permissions)
            self.stdout.write(self.style.SUCCESS(f'Assigned permissions to {group_name}'))

        # CSR: View, Add, Change for Customer and Payment
        csr_perms = list(get_perms(Customer, ['view', 'add', 'change'])) + \
                    list(get_perms(Payment, ['view', 'add', 'change']))
        assign_perms('CSR', csr_perms)

        # Agent: View for Customer and Payment
        agent_perms = list(get_perms(Customer, ['view'])) + \
                      list(get_perms(Payment, ['view']))
        assign_perms('Agent', agent_perms)

        # Technician: View and Change for Customer, View/Change for MikrotikDevice
        tech_perms = list(get_perms(Customer, ['view', 'change'])) + \
                     list(get_perms(MikrotikDevice, ['view', 'change']))
        assign_perms('Technician', tech_perms)

        # Admin: Can be left empty here as Admin usually has is_superuser=True 
        # which grants all permissions implicitly. We still created the group for grouping purposes.

        self.stdout.write(self.style.SUCCESS('Successfully setup RBAC groups and permissions!'))
