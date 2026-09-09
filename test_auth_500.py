import os, django, traceback
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gametech_core.settings")
django.setup()
from django.test.client import Client
from django.contrib.auth.models import User
c = Client()
try:
    user = User.objects.first()
    if user:
        c.force_login(user)
    else:
        print("No users found to test auth!")
    response = c.get("/customers/")
    if response.status_code >= 500:
        print(response.content.decode())
    else:
        print(f"Success! Status: {response.status_code}")
except Exception as e:
    traceback.print_exc()
