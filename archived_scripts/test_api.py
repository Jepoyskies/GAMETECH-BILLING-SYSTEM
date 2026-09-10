import os, sys, django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()
from django.test import RequestFactory
from billing.views.api import api_customer_mikrotik_status
from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.first()
factory = RequestFactory()
req = factory.get('/')
req.user = u
res = api_customer_mikrotik_status(req, 1)
print("STATUS:", res.status_code)
print("CONTENT:", res.content.decode('utf-8'))
