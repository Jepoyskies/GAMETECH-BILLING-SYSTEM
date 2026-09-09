import traceback
from django.test import Client
from billing.models import Customer

client = Client()
client.post('/login/', {'username': 'Admin', 'password': '1234'})

customers = Customer.objects.all()
if customers.exists():
    c = customers.first()
    username = c.pppoe_username or c.full_name
    url = f'/customer/{username}/pay/'
    try:
        resp = client.get(url)
        print(f"Status for {url}: {resp.status_code}")
        if resp.status_code == 500:
            content = resp.content.decode('utf-8', errors='ignore')
            if 'Traceback' in content:
                start = content.find('Traceback')
                print(content[start:start+3000])
    except Exception as e:
        traceback.print_exc()
else:
    print("No customers found to test.")
