import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()

from billing.models import AccountType, Agent

def seed():
    # Account Types
    types = ['Home', 'Business', 'Enterprise']
    for t in types:
        AccountType.objects.get_or_create(type_name=t)
        print(f"Created AccountType: {t}")
        
    # Agents
    agents = [
        {'name': 'Sir Vince', 'email': 'vince@gametech.com'},
        {'name': 'Maam Lai', 'email': 'lai@gametech.com'}
    ]
    
    for a in agents:
        Agent.objects.get_or_create(email=a['email'], defaults={'name': a['name']})
        print(f"Created Agent: {a['name']}")

if __name__ == '__main__':
    seed()
