"""Get the REAL traceback for dispatch_customer_detail_view."""
import traceback

from django.contrib.auth import get_user_model
from django.test import RequestFactory

from billing.models import Customer
import dispatch.views as dv

U = get_user_model()
cust = Customer.objects.first()
print(f"testing with customer {cust.id} {cust.pppoe_username}")

rf = RequestFactory()
req = rf.get(f"/dispatch/customers/{cust.id}/")
req.user = U.objects.filter(is_staff=True).first()

try:
    resp = dv.dispatch_customer_detail_view(req, cust.id)
    print("OK ->", resp.status_code)
except Exception:
    print("=" * 74)
    traceback.print_exc()
    print("=" * 74)
