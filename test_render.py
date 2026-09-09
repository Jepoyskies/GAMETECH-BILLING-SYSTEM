from django.template.loader import render_to_string
from billing.models import Customer
c = Customer.objects.filter(pppoe_username='lab_test').first() or Customer.objects.first()
context = {'customer': c, 'monthly_price': 100.0, 'current_expiry_display': '2026-10-10', 'start_default_str':'2026-10-10', 'end_default_str':'2026-11-10'}
try:
  render_to_string('billing/pay_customer.html', context)
  print('Render Success!')
except Exception as e:
  import traceback
  traceback.print_exc()
