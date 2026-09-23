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
        pppoe_username = request.POST.get('pppoe_username')
        pppoe_password = request.POST.get('pppoe_password')
        try:
            customer = Customer.objects.get(pppoe_username=pppoe_username, pppoe_password=pppoe_password)
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
            return redirect('customer_portal:portal_dashboard')
        except Customer.DoesNotExist:
            messages.error(request, 'Invalid PPPoE username or password.')
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
        elif len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
        elif new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
        else:
            customer.portal_password = new_password
            customer.must_change_password = False
            customer.save()
            messages.success(request, "Password updated successfully! Welcome to your dashboard.")
            return redirect('customer_portal:portal_dashboard')
    return render(request, 'customer_portal/force_change_password.html', {'customer': customer})
