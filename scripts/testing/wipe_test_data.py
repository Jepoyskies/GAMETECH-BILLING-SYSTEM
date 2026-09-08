import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from django.contrib.auth.models import User
from billing.models import Customer, Payment, SystemLog, AuditLog, AddOnRequest, Notification, ImprovementRequest, SmsLog
try:
    from network_manager.models import PPPoESessionLog
except ImportError:
    pass

def wipe_data():
    print("Wiping test data...")
    
    # Delete non-superusers
    deleted_users, _ = User.objects.filter(is_superuser=False).delete()
    print(f"Deleted {deleted_users} non-superusers.")
    
    # Delete ALL Customers
    deleted_customers, _ = Customer.objects.all().delete()
    print(f"Deleted {deleted_customers} customers.")
    
    # Delete all payments
    deleted_payments, _ = Payment.objects.all().delete()
    print(f"Deleted {deleted_payments} payments.")
    
    # Delete all logs and requests
    SystemLog.objects.all().delete()
    AuditLog.objects.all().delete()
    AddOnRequest.objects.all().delete()
    Notification.objects.all().delete()
    ImprovementRequest.objects.all().delete()
    try:
        SMSLog.objects.all().delete()
    except:
        pass
        
    try:
        PPPoESessionLog.objects.all().delete()
    except:
        pass
    
    print("Done wiping data.")

if __name__ == '__main__':
    wipe_data()
