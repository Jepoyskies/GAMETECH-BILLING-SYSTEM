#!/bin/bash
echo "=== recent access codes ==="
docker logs --since 15m gametech-web 2>&1 | grep -oE '" [0-9]{3} ' | sort | uniq -c
echo
echo "=== anything mentioning the agent portal ==="
docker logs --since 15m gametech-web 2>&1 | grep -iE 'agents/portal|Traceback|Internal Server' | tail -20
echo
echo "=== fetch the page server-side and report its status ==="
docker exec gametech-web python -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/staff/agents/portal/19/', timeout=20)
    print('status', r.status)
except Exception as e:
    print('anon fetch ->', type(e).__name__, e)
"
echo
echo "=== does the template render at all? ==="
docker exec gametech-web python manage.py shell -c "
from django.template.loader import get_template
for name in ('billing/agent_portal/dashboard.html',
             'billing/agent_portal/base_agent.html',
             'billing/agent_portal/_my_customers.html'):
    try:
        get_template(name)
        print('OK  ', name)
    except Exception as e:
        print('FAIL', name, '->', e)
" 2>&1 | tail -5