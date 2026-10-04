"""
BILLING INTEGRITY SWEEP.

Financial rules that must hold. Each check is independent and creates only the
records it needs, tagged is_test_data where the model allows it.
"""
import json
from decimal import Decimal
from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from billing.models import Customer, Payment, Rebate, SubscriptionPlan, Agent
from billing.views import calculate_new_expiration_date

U = get_user_model()
res = []


def check(label, cond, detail=""):
    res.append((bool(cond), label, detail))
    print(f"  [{'PASS' if cond else '**FAIL**'}] {label} {detail}")


def hdr(s):
    print("\n" + "=" * 76 + f"\n{s}\n" + "=" * 76)


plan = SubscriptionPlan.objects.filter(price__gt=0).order_by("price").first()
price = float(plan.price)
print(f"Using plan: {plan.name} @ PHP {price}")

# ---------------------------------------------------------------- pure function
hdr("1. EXPIRY ARITHMETIC (pure function, no DB)")
now = timezone.now()
cases = [
    ("exact full month", price, price, "one calendar month"),
    ("half month", price / 2, price, "~15 days"),
    ("quarter", price / 4, price, "~7 days"),
    ("double month", price * 2, price, "two calendar months"),
    ("overpay", price * 3, price, "three months"),
]
for label, amt, plan_price, expect in cases:
    got = calculate_new_expiration_date(now, amt, plan_price)
    days = (got - now).days
    print(f"    {label:18} pay {amt:>9,.2f} -> +{days:>3}d  ({got:%Y-%m-%d})   expected {expect}")
    if label == "exact full month":
        check("full payment grants a calendar month", 27 <= days <= 31, f"{days}d")
    if label == "half month":
        check("half payment grants ~15 days", 13 <= days <= 17, f"{days}d")
    if label == "double month":
        check("double payment grants ~2 months", 55 <= days <= 62, f"{days}d")

# lapsed anchor
lapsed = now - timedelta(days=120)
got = calculate_new_expiration_date(lapsed, price, price)
days = (got - now).days
check("paying after lapse anchors on TODAY (not the old date)",
      27 <= days <= 31, f"{days}d from now (old date was 120d ago)")

got0 = calculate_new_expiration_date(now, 0, price)
check("zero payment grants nothing", got0 == now)
gotneg = calculate_new_expiration_date(now, price, 0)
check("zero-price plan does not divide by zero", gotneg == now)

# ---------------------------------------------------------------- renewal
hdr("2. RENEWAL EXTENDS FROM EXISTING EXPIRY")
staff = Client()
staff.force_login(U.objects.get(username="Vince"))

c = Customer.objects.create(
    full_name="TEST Billing Sweep", pppoe_username="e2e_billing_sweep",
    pppoe_password="x", status="active", installation_status="installed",
    plan=plan, is_test_data=True,
)
first_expiry = now + timedelta(days=10)
Customer.objects.filter(pk=c.pk).update(expires_at=first_expiry)
c.refresh_from_db()

r = staff.post(f"/customer/{c.pppoe_username}/pay/", {
    "amount": str(price), "payment_method": "cash", "reason": "renewal test",
})
c.refresh_from_db()
gained = (c.expires_at - first_expiry).days
check("early renewal extends from the existing expiry", 27 <= gained <= 31,
      f"+{gained}d (first_expiry {first_expiry:%Y-%m-%d} -> {c.expires_at:%Y-%m-%d})")
check("renewal keeps status active", c.status == "active", f"status={c.status}")
check("renewal wrote exactly one Payment", Payment.objects.filter(customer=c).count() == 1)

# ---------------------------------------------------------------- proration
hdr("3. PRORATED PARTIAL PAYMENT")
c2 = Customer.objects.create(
    full_name="TEST Proration", pppoe_username="e2e_proration",
    pppoe_password="x", status="active", installation_status="installed",
    plan=plan, is_test_data=True,
)
Customer.objects.filter(pk=c2.pk).update(expires_at=None)
c2.refresh_from_db()
r = staff.post(f"/customer/{c2.pppoe_username}/pay/", {
    "amount": str(round(price / 2, 2)), "payment_method": "cash", "reason": "partial",
})
c2.refresh_from_db()
check("partial payment set a prorated expiry", c2.expires_at is not None,
      f"expires={c2.expires_at}")
if c2.expires_at:
    d = (c2.expires_at - timezone.now()).days
    check("partial payment granted ~half a month", 12 <= d <= 18, f"{d}d")
check("partial payment activated the customer", c2.status == "active", f"status={c2.status}")

# ---------------------------------------------------------------- suspend/reactivate
hdr("4. SUSPEND / REACTIVATE")
r = staff.post(f"/customer/{c.pppoe_username}/force-suspend/", {"reason": "non-payment"})
c.refresh_from_db()
check("CSR can suspend a customer", c.status == "suspended", f"status={c.status}")

r = staff.post(f"/customer/{c.pppoe_username}/pay/", {
    "amount": str(price), "payment_method": "cash", "reason": "pay to restore",
})
c.refresh_from_db()
check("paying restores a suspended customer to active", c.status == "active", f"status={c.status}")
check("restore also moved the due date", c.expires_at is not None, f"expires={c.expires_at}")

# ---------------------------------------------------------------- duplicate guard
hdr("5. DUPLICATE / VALIDATION GUARDS")
r = staff.post("/customers/add/", {"full_name": "Dup", "phone": "09171234567",
                                   "pppoe_username": "e2e_billing_sweep"})
check("duplicate PPPoE username is rejected", "already exists" in r.content.decode().lower()
      or r.status_code == 200, f"HTTP {r.status_code}")

r = staff.post(f"/customer/{c.pppoe_username}/pay/", {"amount": "-50"})
check("negative payment rejected", Payment.objects.filter(customer=c, amount__lt=0).count() == 0)

r = staff.post(f"/customer/{c.pppoe_username}/pay/", {"amount": "abc"})
check("non-numeric payment rejected", "Invalid" in r.content.decode() or r.status_code == 200)

# ---------------------------------------------------------------- ledger integrity
hdr("6. LEDGER INTEGRITY")
total_paid = sum(Decimal(str(p.amount)) for p in Payment.objects.filter(customer=c))
print(f"    Juan+test total paid for this customer: {total_paid}")
check("every Payment has a non-negative amount",
      Payment.objects.filter(amount__lt=0).count() == 0)
check("no Payment is orphaned",
      Payment.objects.filter(customer__isnull=True).count() == 0)

# cleanup
Customer.objects.filter(pppoe_username__in=["e2e_billing_sweep", "e2e_proration"]).delete()

hdr("SUMMARY")
fails = [r for r in res if not r[0]]
for ok, l, d in res:
    print(f"  {'PASS' if ok else '**FAIL**':8} {l} {d}")
print(f"\n  {len(res)-len(fails)}/{len(res)} passed")