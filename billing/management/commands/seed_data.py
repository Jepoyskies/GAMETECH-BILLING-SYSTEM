from django.core.management.base import BaseCommand
import random
from datetime import timedelta
from django.utils import timezone
from billing.models import SubscriptionPlan, Customer, Payment
from django.db import connection


class Command(BaseCommand):
    help = "Seeds the database with mock data for the dashboard"

    def handle(self, *args, **kwargs):
        self.stdout.write("Deleting old dummy data using raw SQL to bypass signals...")
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM billing_payment;")
            cursor.execute("DELETE FROM billing_customer;")
            cursor.execute("DELETE FROM billing_subscriptionplan;")

        self.stdout.write("Creating Subscription Plans...")
        plans_data = [
            ("pppoe-20m", 1500.00),
            ("pppoe-30m", 2000.00),
            ("pppoe-50m", 2500.00),
            ("pppoe-20m speedboost60", 1800.00),
            ("pppoe-15m_888", 888.00),
            ("pppoe-10m", 1000.00),
            ("pppoe-100m", 3500.00),
            ("pppoe-15m_700", 700.00),
        ]

        plans = {}
        for name, price in plans_data:
            plan = SubscriptionPlan.objects.create(
                name=name,
                speed_up="10 Mbps",
                speed_down="10 Mbps",
                price=price,
                validity_days=30,
            )
            plans[name] = plan

        self.stdout.write("Creating Customers...")
        now = timezone.localtime()

        customers_to_create = []

        # 44 new customers this month
        for i in range(44):
            c = Customer(
                full_name=f"New Customer {i}",
                pppoe_username=f"newcust{i}",
                plan=plans["pppoe-20m"],
                status="active",
            )
            customers_to_create.append(c)

        # Rest 1825 customers older
        for i in range(1825):
            plan_name = random.choices(
                ["pppoe-20m", "pppoe-30m", "pppoe-50m", "pppoe-100m"],
                weights=[1412, 168, 122, 24],
            )[0]

            c = Customer(
                full_name=f"Customer {i}",
                pppoe_username=f"user_{i}",
                plan=plans[plan_name],
                status="active",
                expires_at=now + timedelta(days=random.randint(-10, 30)),
            )
            customers_to_create.append(c)

        Customer.objects.bulk_create(customers_to_create, batch_size=500)
        self.stdout.write(f"Created {Customer.objects.count()} customers.")

        # Update created_at
        idx = 0
        for c in Customer.objects.all():
            if idx < 44:
                # new
                new_date = now - timedelta(days=random.randint(0, 10))
            else:
                new_date = now - timedelta(days=random.randint(30, 365))
            Customer.objects.filter(id=c.id).update(created_at=new_date)
            idx += 1

        all_customers = list(Customer.objects.all())

        self.stdout.write("Creating Payments...")
        payments_to_create = []

        def create_payments_for_target(amount_target, start_dt, end_dt):
            current_amount = 0
            methods = ["Cash", "GCash", "Bank Transfer"]
            while current_amount < amount_target:
                amount = min(
                    random.choice([888, 1000, 1500, 2000]),
                    amount_target - current_amount,
                )
                if amount <= 0:
                    break

                c = random.choice(all_customers)
                delta = end_dt - start_dt
                random_secs = random.randint(0, int(delta.total_seconds()))
                payment_time = start_dt + timedelta(seconds=random_secs)

                p = Payment(
                    customer=c,
                    username=c.pppoe_username,
                    amount=amount,
                    payment_method=random.choice(methods),
                )
                # Need to attach the random date as an attribute so we can update it later
                p._random_date = payment_time
                payments_to_create.append(p)
                current_amount += amount

        t_start = now.replace(hour=0, minute=0, second=0)
        create_payments_for_target(28812.00, t_start, now)

        y_start = t_start - timedelta(days=1)
        create_payments_for_target(42833.00, y_start, t_start)

        w_start = now - timedelta(days=now.weekday())
        w_start = w_start.replace(hour=0, minute=0, second=0)
        if y_start > w_start:
            create_payments_for_target(166268.00, w_start, y_start)

        m_start = now.replace(day=1, hour=0, minute=0, second=0)
        if w_start > m_start:
            create_payments_for_target(519142.00, m_start, w_start)

        last_month_dt = m_start - timedelta(days=15)
        lm_start = last_month_dt.replace(day=1, hour=0, minute=0, second=0)
        create_payments_for_target(1634748.00, lm_start, m_start)

        y_start = now.replace(month=1, day=1, hour=0, minute=0, second=0)
        if lm_start > y_start:
            create_payments_for_target(4201746.53, y_start, lm_start)

        Payment.objects.bulk_create(payments_to_create, batch_size=500)

        # Update created_at
        for p in payments_to_create:
            Payment.objects.filter(id=p.id).update(created_at=p._random_date)

        self.stdout.write(f"Created {Payment.objects.count()} payments.")
        self.stdout.write("Seed complete!")
