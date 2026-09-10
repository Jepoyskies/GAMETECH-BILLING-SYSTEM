import traceback
from django.test import RequestFactory, Client

# Fix session/middleware for test client
client = Client()

# Log in first
login_result = client.post('/login/', {'username': 'Admin', 'password': '1234'})
print(f"Login redirect: {login_result.status_code}")

pages = [
    ('/', 'Dashboard'),
    ('/customers/', 'Customers'),
    ('/plans/', 'Plans'),
    ('/agents/', 'Agents'),
    ('/analytics/', 'Analytics'),
    ('/logs/', 'System Logs'),
    ('/logs/payments/', 'Payment Logs'),
    ('/notifications/', 'Notifications'),
    ('/improvement-requests/', 'Improvement Requests'),
    ('/changelog/', 'Changelog'),
    ('/settings/', 'Settings'),
    ('/geomap/', 'Geomap'),
]

for url, name in pages:
    try:
        resp = client.get(url)
        if resp.status_code == 500:
            print(f"[500 ERROR] {name} ({url})")
            # Get traceback from response
            if hasattr(resp, 'content'):
                content = resp.content.decode('utf-8', errors='ignore')
                # Print a portion with the error
                if 'Traceback' in content:
                    start = content.find('Traceback')
                    print(content[start:start+2000])
                elif 'Exception' in content:
                    start = content.find('Exception')
                    print(content[start:start+1000])
        elif resp.status_code == 200:
            print(f"[OK 200] {name} ({url})")
        else:
            print(f"[{resp.status_code}] {name} ({url})")
    except Exception as e:
        print(f"[CRASH] {name} ({url}): {e}")
        traceback.print_exc()
