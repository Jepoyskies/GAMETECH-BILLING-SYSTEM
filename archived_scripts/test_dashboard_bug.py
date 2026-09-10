import os
import django
import sys
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from django.test import RequestFactory
from billing.views.dashboard import dashboard_view
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware

factory = RequestFactory()
request = factory.get('/')
request.user = User.objects.filter(is_superuser=True).first()
setattr(request, 'session', {})
messages = FallbackStorage(request)
setattr(request, '_messages', messages)

try:
    response = dashboard_view(request)
    print('STATUS:', response.status_code)
except Exception as e:
    traceback.print_exc()
