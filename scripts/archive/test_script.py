from billing.models import Customer
from network_manager.services import MikrotikAPI

c = Customer.objects.filter(pppoe_username__icontains='lab_test').first()
if not c:
    c = Customer.objects.filter(full_name__icontains='lab_test').first()

if c:
    print('Found customer:', c.pppoe_username)
    api = MikrotikAPI(c.mikrotik_device)
    target_profile = c.plan.name if c.plan else 'default'
    print('Target profile:', target_profile)
    success, msg = api.add_pppoe_user(
        name=c.pppoe_username,
        password=c.pppoe_password,
        profile=target_profile,
        comment='Test',
        disabled='no'
    )
    print('Add PPPoE result:', success, msg)
else:
    print('Customer lab_test not found.')
