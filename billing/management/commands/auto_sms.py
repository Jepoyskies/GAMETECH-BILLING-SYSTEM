import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from billing.models import Customer

class Command(BaseCommand):
    help = 'Sends automated SMS to customers expiring within 3 days via Semaphore API'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        three_days_from_now = now + timedelta(days=3)
        
        # Find customers expiring in the next 3 days who haven't received an SMS yet
        target_customers = Customer.objects.filter(
            expires_at__range=(now, three_days_from_now),
            sms_sent_at__isnull=True
        ).exclude(phone__exact='')

        if not target_customers.exists():
            self.stdout.write(self.style.WARNING("No customers need SMS reminders today."))
            return

        semaphore_apikey = "a1be64e85146a946d40aeb1677d37a48"
        count = 0

        for customer in target_customers:
            expiry_str = customer.expires_at.strftime('%b %d, %Y')
            message = f"Hello {customer.full_name}! Your Unli Fiber subscription will expire on {expiry_str}. Kindly renew soon to avoid disconnection. Thank you!"
            
            payload = {
                'apikey': semaphore_apikey,
                'number': customer.phone,
                'message': message,
                'sendername': 'SEMAPHORE' # Change if Gametech has a registered sender name
            }

            try:
                # Uncomment the lines below to ACTUALLY send the SMS (disabled for dev so we don't spam people)
                # response = requests.post('https://api.semaphore.co/api/v4/messages', data=payload)
                # if response.status_code == 200:
                
                customer.sms_sent_at = now
                customer.save(update_fields=['sms_sent_at'])
                count += 1
                self.stdout.write(self.style.SUCCESS(f"✅ SMS sent to {customer.pppoe_username} ({customer.phone})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Failed to send SMS to {customer.pppoe_username}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f'🎉 Auto SMS process complete. Total sent: {count}'))