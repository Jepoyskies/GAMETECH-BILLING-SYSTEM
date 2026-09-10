import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()
from django.test import RequestFactory
from billing.views.core import dashboard
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware

factory = RequestFactory()
request = factory.get('/')
request.user = User.objects.filter(is_superuser=True).first()
setattr(request, 'session', 'session')
messages = FallbackStorage(request)
setattr(request, '_messages', messages)

try:
    response = dashboard(request)
    print('STATUS:', response.status_code)
    if response.status_code == 500:
        print('CONTENT:', response.content.decode('utf-8'))
except Exception as e:
    import traceback
    traceback.print_exc()
