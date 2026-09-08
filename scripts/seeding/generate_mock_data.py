import os
import django
import random
from datetime import timedelta, datetime
from django.utils import timezone
from billing.models import Customer, SubscriptionPlan, Payment, Barangay, AccountType

def run():
    print("Generating mock data...")

    # Basic Lookups
    brgy, _ = Barangay.objects.get_or_create(name="Poblacion")
    acc_type, _ = AccountType.objects.get_or_create(type_name="Residential")
    
    # Plans
    plan1, _ = SubscriptionPlan.objects.get_or_create(name="Fiber 50Mbps", defaults={'price': 1500, 'speed_up': '50', 'speed_down': '50'})
    plan2, _ = SubscriptionPlan.objects.get_or_create(name="Fiber 100Mbps", defaults={'price': 2500, 'speed_up': '100', 'speed_down': '100'})
    plans = [plan1, plan2]

    today = timezone.localtime().date()
    now = timezone.localtime()

    payment_methods = ['Cash', 'GCash', 'Bank Transfer']
    method_weights = [0.3, 0.6, 0.1]

    print("Generating Customers...")
    customers = []
    # Generate 150 Customers
    for i in range(1, 151):
        c_date = now - timedelta(days=random.randint(0, 180)) # created anytime in last 6 months
        c_plan = random.choice(plans)
        c, created = Customer.objects.get_or_create(
            pppoe_username=f"user_{i:03d}",
            defaults={
                'full_name': f"Mock User {i:03d}",
                'plan': c_plan,
                'barangay': brgy,
                'account_type': acc_type,
            }
        )
        if created:
            c.created_at = c_date
            c.save()
        customers.append(c)

    print("Generating Payments for Last Month...")
    # Generate Payments for Last Month
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    
    # 60% of customers paid last month
    for c in random.sample(customers, int(len(customers)*0.6)):
        pay_date = last_month_start + timedelta(days=random.randint(1, 28))
        Payment.objects.create(
            customer=c,
            amount=c.plan.price if c.plan else 1500,
            payment_method=random.choices(payment_methods, method_weights)[0],
            created_at=timezone.make_aware(datetime.combine(pay_date, datetime.min.time()))
        )

    print("Generating Payments for This Month...")
    # Generate Payments for This Month
    this_month_start = today.replace(day=1)
    
    # 85% of customers paid this month (High collection rate + Revenue Growth)
    for c in random.sample(customers, int(len(customers)*0.85)):
        # distribute days across this month up to today
        max_days = min(today.day, 28) - 1
        if max_days < 1: max_days = 1
        pay_date = this_month_start + timedelta(days=random.randint(0, max_days))
        
        # force some payments specifically in the last 7 days to populate the week chart!
        if random.random() < 0.4:
            pay_date = today - timedelta(days=random.randint(0, 6))

        Payment.objects.create(
            customer=c,
            amount=c.plan.price if c.plan else 1500,
            payment_method=random.choices(payment_methods, method_weights)[0],
            created_at=timezone.make_aware(datetime.combine(pay_date, datetime.min.time()))
        )

    print("Mock data generated successfully!")

if __name__ == '__main__':
    run()
