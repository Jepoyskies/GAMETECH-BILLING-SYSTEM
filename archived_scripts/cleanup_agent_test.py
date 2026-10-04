"""Clean up the verification payment, keep the demo coherent for a visual check."""
from django.utils import timezone
from billing.models import Customer, Payment

stray = Payment.objects.filter(reason="verify_agent_portal")
n, _ = stray.delete()
print(f"deleted {n} stray verification payment(s)")

cust = Customer.objects.filter(pppoe_username="delacruz_juan_e2e").first()
if cust:
    # A coherent picture for the visual check: referred by Martin, line not
    # installed yet, nothing paid yet. Installing and billing are separate
    # facts, and payment-gated activation means he cannot be 'active' unpaid.
    cust.status = "pending"
    cust.installation_status = "pending"
    cust.expires_at = None
    cust.outstanding_balance = 0
    cust.save()
    print(f"{cust.pppoe_username}: status={cust.status} "
          f"install={cust.installation_status} agent={cust.agent} "
          f"payments={Payment.objects.filter(username=cust.pppoe_username).count()}")
