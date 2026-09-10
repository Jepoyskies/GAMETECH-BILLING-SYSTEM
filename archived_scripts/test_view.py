import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()
from django.test import RequestFactory
from billing.views.payments import pay_customer_view
from django.contrib.auth.models import User
from billing.models import Customer
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware

factory = RequestFactory()
request = factory.get('/customer/lab_test/pay/')
request.user = User.objects.filter(is_superuser=True).first()
setattr(request, 'session', 'session')
messages = FallbackStorage(request)
setattr(request, '_messages', messages)

cust = Customer.objects.filter(pppoe_username='lab_test').first()
if not cust:
    cust = Customer.objects.first()

try:
    response = pay_customer_view(request, cust.pppoe_username)
    print('STATUS:', response.status_code)
    if response.status_code == 500:
        print('CONTENT:', response.content.decode('utf-8'))
except Exception as e:
    import traceback
    traceback.print_exc()
