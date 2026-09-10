from django.test import Client
from django.contrib.auth.models import User
try:
    c = Client()
    c.force_login(User.objects.first())
    response = c.get('/customers/view/35/')
    print('STATUS CODE:', response.status_code)
    if response.status_code == 500:
        print("CONTENT:", response.content.decode('utf-8'))
except Exception as e:
    import traceback
    traceback.print_exc()
