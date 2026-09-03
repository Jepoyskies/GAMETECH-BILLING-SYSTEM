import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gametech_core.settings')
django.setup()
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI
d = MikrotikDevice.objects.first()
api = MikrotikAPI(d)
users = api.get_active_pppoe_users()
print('users:', len(users))
if users:
    u = users[0]
    name = u.get('name')
    if name:
        res = api._get_api().get_resource('/interface').call('monitor-traffic', {'interface': f'<pppoe-{name}>', 'once': ''})
        print('Single interface res:', res)
    names = [f'<pppoe-{x.get("name")}>' for x in users[:3] if x.get('name')]
    if names:
        try:
            res2 = api._get_api().get_resource('/interface').call('monitor-traffic', {'interface': ','.join(names), 'once': ''})
            print('Multi interface res:', len(res2))
        except Exception as e:
            print('Multi interface error:', e)
