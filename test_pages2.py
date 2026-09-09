import traceback
from django.test import Client

client = Client()

login_result = client.post('/login/', {'username': 'Admin', 'password': '1234'})
print(f"Login redirect: {login_result.status_code}")

pages = [
    # Network Manager
    ('/network/', 'Network Dashboard'),
    ('/devices/', 'Devices'),
    ('/napboxes/', 'Napboxes'),
    ('/mikrotik-active-users/', 'MikroTik Active Users'),
    ('/live-monitoring/', 'Live Monitoring'),
    ('/downdetector/', 'Downdetector'),
    # Dispatch
    ('/dispatch/', 'Dispatch'),
    # Payments area
    ('/logs/rebates/', 'Rebate Logs'),
    ('/add-ons/', 'Add-ons'),
    ('/cignal-play/', 'Cignal Play'),
    ('/payment-portal/', 'Payment Portal'),
    ('/auto-suspend/', 'Auto Suspend'),
    ('/staff/', 'Staff'),
    ('/mac-history/', 'MAC History'),
    # Audit logs
    ('/logs/payment-addons/', 'Payment Addon Logs'),
    ('/sms/', 'SMS Messaging'),
    # Settings pages
    ('/settings/barangays/', 'Barangays'),
    ('/settings/account-types/', 'Account Types'),
    ('/settings/templates/', 'Message Templates'),
    ('/settings/backup/', 'Backup'),
    ('/settings/import/', 'Import Data'),
    ('/admin-panel/', 'Admin Panel'),
]

for url, name in pages:
    try:
        resp = client.get(url)
        if resp.status_code == 500:
            print(f"[500 ERROR] {name} ({url})")
            if hasattr(resp, 'content'):
                content = resp.content.decode('utf-8', errors='ignore')
                if 'Traceback' in content:
                    start = content.find('Traceback')
                    print(content[start:start+1500])
                elif 'Exception' in content:
                    start = content.find('Exception')
                    print(content[start:start+800])
        elif resp.status_code == 200:
            print(f"[OK 200] {name} ({url})")
        elif resp.status_code in [301, 302]:
            print(f"[REDIRECT {resp.status_code}] {name} ({url}) -> {resp.get('Location', '?')}")
        elif resp.status_code == 404:
            print(f"[404] {name} ({url})")
        else:
            print(f"[{resp.status_code}] {name} ({url})")
    except Exception as e:
        print(f"[CRASH] {name} ({url}): {e}")
        traceback.print_exc()
