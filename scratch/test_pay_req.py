import requests
session = requests.Session()
r = session.post('http://localhost:8000/login/', data={'username': 'Admin', 'password': '1234'})
print("Login status:", r.status_code)
# Get a username using an API or just use test_pay logic from database
