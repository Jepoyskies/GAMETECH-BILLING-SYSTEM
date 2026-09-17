import requests

session = requests.Session()

# Test 1: Login page (unauthenticated)
r = session.get('http://localhost:8000/login/', allow_redirects=False)
print(f"Login page: {r.status_code}")
if r.status_code == 500:
    print(r.text[:500])

# Test 2: Dashboard (unauthenticated - should redirect)
r2 = session.get('http://localhost:8000/', allow_redirects=False)
print(f"Dashboard (no auth): {r2.status_code}")

# Test 3: Login and test pages
from bs4 import BeautifulSoup
r = session.get('http://localhost:8000/login/')
soup = BeautifulSoup(r.text, 'html.parser')
csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
if csrf_input:
    csrf_token = csrf_input['value']
    login_data = {
        'username': 'JillianAthea',
        'password': 'admin',
        'csrfmiddlewaretoken': csrf_token
    }
    r3 = session.post('http://localhost:8000/login/', data=login_data, headers={'Referer': 'http://localhost:8000/login/'}, allow_redirects=False)
    print(f"Login POST: {r3.status_code}")
    
    # Test dashboard after login
    r4 = session.get('http://localhost:8000/', allow_redirects=False)
    print(f"Dashboard (authed): {r4.status_code}")
    if r4.status_code == 500:
        print("=== DASHBOARD 500 ERROR ===")
        print(r4.text[:2000])
    
    # Test customers
    r5 = session.get('http://localhost:8000/customers/', allow_redirects=False)
    print(f"Customers (authed): {r5.status_code}")
    if r5.status_code == 500:
        print("=== CUSTOMERS 500 ERROR ===")
        print(r5.text[:2000])
else:
    print("Could not find CSRF token!")