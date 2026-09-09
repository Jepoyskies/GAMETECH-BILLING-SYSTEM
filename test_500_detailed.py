from django.test import Client
from django.contrib.auth.models import User
from billing.models import Customer
c = Client()
u = User.objects.filter(is_superuser=True).first()
c.force_login(u)
cust = Customer.objects.filter(pppoe_username='lab_test').first()
if not cust:
    cust = Customer.objects.first()
resp = c.get(f'/customer/{cust.pppoe_username}/pay/')
print('Status:', resp.status_code)
if resp.status_code == 500:
    print(resp.content.decode('utf-8'))
