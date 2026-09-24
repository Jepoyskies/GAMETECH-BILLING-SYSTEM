from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from billing.models import Customer, Agent, SubscriptionPlan, Barangay, SystemAdmin
from network_manager.models import MikrotikDevice
from dispatch.models import JobTicket

TEST_TAG = "[TEST-DATA]"
TEST_PREFIX = "test_dispatch_"


class Command(BaseCommand):
    help = "Seeds fake test data (customers, agents, technicians, devices, tickets) safe for ROUTER_DRY_RUN, with 1-step cleanup."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Deletes all fake test data created by this command.",
        )

    def handle(self, *args, **options):
        if options["cleanup"]:
            self.stdout.write("Cleaning up fake dispatch test data...")
            deleted_tickets = JobTicket.objects.filter(
                concern__icontains=TEST_TAG
            ).delete()[0]
            deleted_customers = Customer.objects.filter(
                pppoe_username__startswith=TEST_PREFIX
            ).delete()[0]
            deleted_agents = Agent.objects.filter(
                name__icontains=TEST_TAG
            ).delete()[0]
            deleted_tech_admins = SystemAdmin.objects.filter(
                username__startswith=TEST_PREFIX
            ).delete()[0]
            deleted_tech_users = User.objects.filter(
                username__startswith=TEST_PREFIX
            ).delete()[0]
            deleted_devices = MikrotikDevice.objects.filter(
                device_name__icontains=TEST_TAG
            ).delete()[0]

            self.stdout.write(
                self.style.SUCCESS(
                    f"Cleanup complete. Deleted: {deleted_tickets} tickets, "
                    f"{deleted_customers} customers, {deleted_agents} agents, "
                    f"{deleted_tech_admins} technicians, {deleted_devices} test devices."
                )
            )
            return

        self.stdout.write("Seeding fake dispatch test data (ROUTER_DRY_RUN safe)...")

        # 1. Test Barangay & Plan
        barangay, _ = Barangay.objects.get_or_create(name="Bulua Test Zone")
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="GTipid Fiber 1000",
            defaults={
                "price": 1000.00,
                "speed_up": "35 Mbps",
                "speed_down": "35 Mbps",
            },
        )

        # 2. Test Router
        device, _ = MikrotikDevice.objects.get_or_create(
            ip_address="192.168.88.99",
            defaults={
                "device_name": f"CCR2004 Lab {TEST_TAG}",
                "api_username": "admin",
                "api_password": "dry_run_password",
                "api_port": 8728,
                "health_status": "Excellent",
            },
        )

        # 3. Test Agent
        agent, _ = Agent.objects.get_or_create(
            phone="09181112233",
            defaults={
                "name": f"Maria Santos {TEST_TAG}",
                "email": "maria_test@gametech.local",
                "is_test_data": True,
            },
        )

        # 4. Test Technicians
        techs = [
            ("alpha", "Juan Tech"),
            ("bravo", "Pedro Tech"),
        ]
        created_techs = []
        for code, full_name in techs:
            username = f"{TEST_PREFIX}tech_{code}"
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={"first_name": full_name, "is_staff": True},
            )
            if not user.password:
                user.set_password("TechPass123!")
                user.save()

            tech_admin, _ = SystemAdmin.objects.get_or_create(
                username=username,
                defaults={
                    "user": user,
                    "full_name": f"{full_name} {TEST_TAG}",
                    "email": f"{username}@gametech.local",
                    "role": "Technician",
                    "status": "Active",
                },
            )
            created_techs.append(tech_admin)

        # 5. Test Customers
        subscribers = [
            (
                "sub_alpha",
                "Alice Test",
                "active",
                "installed",
                "09171110001",
                agent,
            ),
            (
                "sub_beta",
                "Bob Test",
                "pending",
                "pending_install",
                "09171110002",
                agent,
            ),
            (
                "sub_gamma",
                "Charlie Test",
                "suspended",
                "installed",
                "09171110003",
                None,
            ),
        ]
        created_customers = []
        for suffix, name, status, install_status, phone, assigned_agent in subscribers:
            pppoe = f"{TEST_PREFIX}{suffix}"
            customer, _ = Customer.objects.get_or_create(
                pppoe_username=pppoe,
                defaults={
                    "full_name": f"{name} {TEST_TAG}",
                    "phone": phone,
                    "address": f"Purok 1, Bulua {TEST_TAG}",
                    "barangay": barangay,
                    "plan": plan,
                    "mikrotik_device": device,
                    "agent": assigned_agent,
                    "status": status,
                    "installation_status": install_status,
                    "pppoe_password": "testpppoepassword",
                    "is_test_data": True,
                },
            )
            created_customers.append(customer)

        # 6. Test JobTickets
        JobTicket.objects.get_or_create(
            customer=created_customers[1],
            ticket_type="INSTALLATION",
            defaults={
                "client_name": created_customers[1].full_name,
                "account_no": created_customers[1].pppoe_username,
                "contact_number": created_customers[1].phone,
                "address": created_customers[1].address,
                "barangay": barangay.name,
                "plan_package": plan.name,
                "concern": f"Standard install at Purok 1 Bulua. {TEST_TAG}",
                "status": "ASSIGNED",
                "source_tab": "INTERNET_INSTALL",
                "is_test_data": True,
            },
        )

        JobTicket.objects.get_or_create(
            customer=created_customers[0],
            ticket_type="REPAIR",
            defaults={
                "client_name": created_customers[0].full_name,
                "account_no": created_customers[0].pppoe_username,
                "contact_number": created_customers[0].phone,
                "address": created_customers[0].address,
                "barangay": barangay.name,
                "plan_package": plan.name,
                "concern": f"Subscriber reports fiber cut. {TEST_TAG}",
                "status": "IN_PROGRESS",
                "source_tab": "CLIENT_CONCERNS",
                "is_test_data": True,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded fake test data:\n"
                f"  - Agent: {agent.name}\n"
                f"  - Technicians: {len(created_techs)}\n"
                f"  - Customers: {len(created_customers)} ({', '.join(c.pppoe_username for c in created_customers)})\n"
                f"  - Device: {device.device_name}\n"
                f"Run 'python manage.py seed_dispatch_test_data --cleanup' anytime to remove."
            )
        )
