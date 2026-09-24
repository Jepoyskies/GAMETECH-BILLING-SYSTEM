from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.core.cache import cache
from django.contrib.sessions.models import Session
from billing.models import Customer

import logging
logger = logging.getLogger(__name__)


def portal_login(request):
    # If already logged in, redirect to dashboard
    if request.session.get('customer_id'):
        return redirect('customer_portal:portal_dashboard')

    if request.method == 'POST':
        from billing.security import (
            get_client_ip,
            is_account_or_ip_locked,
            record_login_failure,
            clear_login_failures,
        )
        import re
        from django.db.models import Q

        username = (request.POST.get('pppoe_username') or request.POST.get('username') or '').strip()
        password = request.POST.get('pppoe_password') or request.POST.get('password') or ''
        ip = get_client_ip(request)

        # 1. Check account / IP lockout
        is_locked, remaining = is_account_or_ip_locked(username, ip)
        if is_locked:
            minutes = max(1, (remaining + 59) // 60)
            messages.error(
                request,
                f"Too many failed login attempts. Account/IP temporarily locked. Please try again in {minutes} minute(s)."
            )
            return render(request, 'customer_portal/portal_login.html')

        # 2. Query customer by pppoe_username OR registered phone (NO full_name)
        clean_digits = re.sub(r'\D', '', username)
        phone_candidates = [username]
        if clean_digits:
            phone_candidates.extend([
                clean_digits,
                "0" + clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits,
                "+63" + clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits,
                "63" + clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits,
            ])

        customer = Customer.objects.filter(
            Q(pppoe_username__iexact=username) | Q(phone__in=phone_candidates)
        ).first()

        # 3. Verify portal password (PPPoE password is NOT accepted)
        if customer and customer.check_portal_password(password):
            clear_login_failures(username, ip)

            # Check if temporary password has expired (> 7 days)
            if customer.is_temp_password_expired():
                messages.error(
                    request,
                    "Your temporary password has expired (validity: 7 days). Please contact Gametech support to reset your credentials."
                )
                return render(request, 'customer_portal/portal_login.html')

            request.session['customer_id'] = customer.id
            request.session['customer_last_seen'] = timezone.now().isoformat()
            try:
                now = timezone.now()
                cache.set(f"seen_customer_{customer.id}", now, 300)
                active = cache.get("active_portal_customers") or {}
                active[str(customer.id)] = now.isoformat()
                cache.set("active_portal_customers", active, 600)
            except Exception:
                pass

            if customer.must_change_password:
                return redirect('customer_portal:force_change_password')

            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url if next_url else 'customer_portal:portal_dashboard')

        # Failed attempt: record failure and increment counter
        is_now_locked, attempts, lock_dur = record_login_failure(username, ip)
        if is_now_locked:
            messages.error(
                request,
                "Your account or IP has been locked for 15 minutes due to 5 consecutive failed login attempts."
            )
        else:
            remaining_attempts = max(1, 5 - attempts)
            messages.error(
                request,
                f"Invalid username or portal password. ({remaining_attempts} attempt{'s' if remaining_attempts != 1 else ''} remaining before lockout)"
            )

    return render(request, 'customer_portal/portal_login.html')


def portal_logout(request):
    customer_id = request.session.get('customer_id')
    if customer_id:
        try:
            cache.delete(f"seen_customer_{customer_id}")
            active = cache.get("active_portal_customers") or {}
            active.pop(str(customer_id), None)
            active.pop(int(customer_id), None)
            cache.set("active_portal_customers", active, 600)
        except Exception:
            pass
        try:
            for s in Session.objects.filter(expire_date__gte=timezone.now()):
                try:
                    s_data = s.get_decoded()
                    if str(s_data.get("customer_id")) == str(customer_id):
                        s.delete()
                except Exception:
                    pass
        except Exception:
            pass

    try:
        from django.contrib.messages import get_messages
        storage = get_messages(request)
        for _ in storage:
            pass
        storage.used = True
        storage._queued_messages = []
    except Exception:
        pass
    request.session.flush()
    return redirect('customer_portal:portal_login')


def force_change_password(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('customer_portal:portal_login')
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect('customer_portal:portal_login')
    if not customer.must_change_password:
        return redirect('customer_portal:portal_dashboard')

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not new_password or not confirm_password:
            messages.error(request, "Please fill in all fields.")
        elif new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
        else:
            from billing.validators import validate_password_policy
            from django.core.exceptions import ValidationError
            try:
                validate_password_policy(new_password, user_or_customer=customer)
                customer.set_portal_password(new_password)
                customer.must_change_password = False
                customer.temp_password_created_at = None
                customer.save(update_fields=['portal_password_hash', 'portal_password', 'must_change_password', 'temp_password_created_at'])
                messages.success(request, "Password updated successfully! Welcome to your dashboard.")
                return redirect('customer_portal:portal_dashboard')
            except ValidationError as e:
                messages.error(request, str(e.message))

    return render(request, 'customer_portal/force_change_password.html', {'customer': customer})

