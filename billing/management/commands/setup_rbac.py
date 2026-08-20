from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from billing.models import Customer, JobOrder, Agent, Payment
from django.core.management.base import CommandError

class Command(BaseCommand):
    help = 'Creates default groups and permissions for the Gametech RBAC system'

    def handle(self, *args, **options):
        # 1. Create Groups
        admin_group, _ = Group.objects.get_or_create(name='Admin') # Though Admins are usually superusers, good to have a group
        technician_group, _ = Group.objects.get_or_create(name='Technician')
        agent_group, _ = Group.objects.get_or_create(name='Agent')
        csr_group, _ = Group.objects.get_or_create(name='CSR')

        try:
            # 2. Get Content Types
            customer_ct = ContentType.objects.get_for_model(Customer)
            job_order_ct = ContentType.objects.get_for_model(JobOrder)
            payment_ct = ContentType.objects.get_for_model(Payment)

            # 3. Assign Permissions
            
            # Technician
            tech_permissions = [
                Permission.objects.get(codename='view_customer', content_type=customer_ct),
                Permission.objects.get(codename='change_joborder', content_type=job_order_ct),
                Permission.objects.get(codename='view_joborder', content_type=job_order_ct),
            ]
            technician_group.permissions.set(tech_permissions)
            
            # Agent
            agent_permissions = [
                Permission.objects.get(codename='add_customer', content_type=customer_ct),
                Permission.objects.get(codename='view_customer', content_type=customer_ct),
                Permission.objects.get(codename='change_customer', content_type=customer_ct),
            ]
            agent_group.permissions.set(agent_permissions)

            # CSR
            csr_permissions = [
                Permission.objects.get(codename='view_customer', content_type=customer_ct),
                Permission.objects.get(codename='change_customer', content_type=customer_ct),
                Permission.objects.get(codename='add_joborder', content_type=job_order_ct),
                Permission.objects.get(codename='change_joborder', content_type=job_order_ct),
                Permission.objects.get(codename='view_joborder', content_type=job_order_ct),
                Permission.objects.get(codename='view_payment', content_type=payment_ct),
            ]
            csr_group.permissions.set(csr_permissions)

            self.stdout.write(self.style.SUCCESS('Successfully setup RBAC groups and permissions.'))
        except Exception as e:
            raise CommandError(f'Error setting up RBAC: {e}. Ensure you have run migrations first.')
