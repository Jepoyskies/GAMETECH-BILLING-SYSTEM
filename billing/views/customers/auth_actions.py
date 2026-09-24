"""
Customer authentication and credential management actions.
Handles secure portal password resets, temporary password generation, and SMS relay.
"""

from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from billing.models import Customer, SystemLog, SmsLog
from billing.validators import generate_temp_password
from billing.views import send_semaphore_sms


@login_required
def reset_customer_portal_password(request, customer_id):
    """
    Resets a customer's portal password:
    1. Generates cryptographically secure 10-char temporary password (letters+numbers).
    2. Stores PBKDF2 hash in portal_password_hash (blanks plaintext).
    3. Sets must_change_password=True and temp_password_created_at=now.
    4. Dispatches SMS via existing Semaphore wrapper (non-blocking).
    5. Stores temp password in session to be displayed ONCE on customer view.
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
        sms_sent = False
        sms_response_text = ""

        if customer.phone:
            message_body = (
                f"Gametech Unli Fiber: Your portal temporary password has been reset.\n"
                f"Username: {login_id}\n"
                f"Temp Password: {temp_pw}\n"
                f"Valid for 7 days. You will be prompted to set a new password upon login.\n"
                f"Access portal: gametech.com.ph"
            )
            # Mask password in log
            masked_body = (
                f"Gametech Unli Fiber: Your portal temporary password has been reset.\n"
                f"Username: {login_id}\n"
                f"Temp Password: [REDACTED]\n"
                f"Valid for 7 days. You will be prompted to set a new password upon login.\n"
                f"Access portal: gametech.com.ph"
            )
            try:
                sms_response_text, sms_sent = send_semaphore_sms(customer.phone, message_body)
                SmsLog.objects.create(
                    phone=customer.phone,
                    message=masked_body,
                    status="Sent" if sms_sent else "Failed",
                    response=sms_response_text[:255] if sms_response_text else "",
                )
            except Exception as e:
                sms_sent = False
                try:
                    SmsLog.objects.create(
                        phone=customer.phone,
                        message=masked_body,
                        status="Failed",
                        response=str(e)[:255],
                    )
                except Exception:
                    pass

        # Log action without plain password
        try:
            SystemLog.objects.create(
                table_name="Customer",
                record_id=str(customer.id),
                action="RESET_PORTAL_PASSWORD",
                changed_by=request.user.username,
                target_name=customer.full_name,
                old_data=f"PPPoE: {customer.pppoe_username}",
                new_data=f"Reset portal password. New 7-day temp password created. SMS Sent: {sms_sent}",
            )
        except Exception:
            pass

        # Store in session to display ONCE on confirmation view
        request.session["customer_temp_password_display"] = {
            "customer_id": customer.id,
            "username": login_id,
            "temp_password": temp_pw,
            "sms_sent": sms_sent,
        }

        if sms_sent:
            messages.success(
                request,
                f"Portal password for {customer.full_name} has been reset. Temporary credentials sent via SMS and displayed below."
            )
        else:
            messages.warning(
                request,
                f"Portal password for {customer.full_name} has been reset. (SMS could not be delivered; please relay the temporary password shown below)."
            )

    return redirect("view_customer", customer_id=customer.id)
