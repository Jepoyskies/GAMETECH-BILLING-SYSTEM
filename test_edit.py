import traceback
from django.test import Client

client = Client()
client.post('/login/', {'username': 'Admin', 'password': '1234'})

# Test edit customer page
try:
    resp = client.get('/customers/edit/1/')
    print(f"Status: {resp.status_code}")
    if resp.status_code == 500:
        content = resp.content.decode('utf-8', errors='ignore')
        if 'Traceback' in content:
            start = content.find('Traceback')
            print(content[start:start+3000])
        elif 'Exception' in content:
            start = content.find('Exception')
            print(content[start:start+2000])
        else:
            print(content[:3000])
except Exception as e:
    traceback.print_exc()

# Also test view_customer
try:
    resp = client.get('/customers/view/1/')
    print(f"\nView Customer Status: {resp.status_code}")
    if resp.status_code == 500:
        content = resp.content.decode('utf-8', errors='ignore')
        if 'Traceback' in content:
            start = content.find('Traceback')
            print(content[start:start+3000])
except Exception as e:
    traceback.print_exc()

# Test add customer
try:
    resp = client.get('/customers/add/')
    print(f"\nAdd Customer Status: {resp.status_code}")
    if resp.status_code == 500:
        content = resp.content.decode('utf-8', errors='ignore')
        if 'Traceback' in content:
            start = content.find('Traceback')
            print(content[start:start+3000])
except Exception as e:
    traceback.print_exc()
