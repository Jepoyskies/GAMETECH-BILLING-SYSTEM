"""
Customer authentication and credential management actions.
Handles secure portal password resets and temporary password generation.
"""

from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from billing.models import Customer, SystemLog
from billing.validators import generate_temp_password


@login_required
def reset_customer_portal_password(request, customer_id):
    """
    Resets a customer's portal password:
    1. Generates cryptographically secure 10-char temporary password (letters+numbers).
    2. Stores PBKDF2 hash in portal_password_hash (blanks plaintext).
    3. Sets must_change_password=True and temp_password_created_at=now.
    4. Stores temp password in session to be displayed ONCE on customer view,
       for staff to relay directly. No SMS is sent (per-call cost, no benefit).
    """
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == "POST":
        temp_pw = generate_temp_password(10)
        customer.set_portal_password(temp_pw)
        customer.must_change_password = True
        customer.temp_password_created_at = timezone.now()
        customer.save(update_fields=[
            "portal_password_hash",
            "portal_password",
            "must_change_password",
            "temp_password_created_at",
        ])

        login_id = customer.pppoe_username or customer.phone

        # Log action without plain password
        try:
            SystemLog.objects.create(
                table_name="Customer",
                record_id=str(customer.id),
                action="RESET_PORTAL_PASSWORD",
                changed_by=request.user.username,
                target_name=customer.full_name,
                old_data=f"PPPoE: {customer.pppoe_username}",
                new_data="Reset portal password. New 7-day temp password created and shown to staff once.",
            )
        except Exception:
            pass

        # Store in session to display ONCE on confirmation view
        request.session["customer_temp_password_display"] = {
            "customer_id": customer.id,
            "username": login_id,
            "temp_password": temp_pw,
        }

        messages.success(
            request,
            f"Portal password for {customer.full_name} has been reset. "
            f"Relay the temporary password shown below to the customer."
        )

    return redirect("view_customer", customer_id=customer.id)
