from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
    permission_required,
)
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from billing.decorators import role_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, Max
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime
from billing.models import (
    SystemAdmin,
    SubscriptionPlan,
    Agent,
    AccountType,
    Customer,
    Barangay,
    Payment,
    Rebate,
    SystemLog,
    SmsLog,
    CignalPlay,
    AuditLog,
    AddOnRequest,
    Notification,
    ImprovementRequest,
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar


@login_required
def agent_list(request):
    from django.db.models import Count
    agents = Agent.objects.annotate(
        customer_count=Count('customer')
    ).order_by("name")

    total_agents = agents.count()
    active_agents = sum(1 for a in agents if a.customer_count > 0)
    total_referrals = sum(a.customer_count for a in agents)
    total_commission = sum(a.claimable_commission for a in agents)

    return render(
        request,
        "billing/agents.html",
        {
            "agents": agents,
            "total_agents": total_agents,
            "active_agents": active_agents,
            "total_referrals": total_referrals,
            "total_commission": total_commission,
        },
    )


@login_required
@role_required(["Admin", "Editor"])
def add_agent(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")

        # Hash password if provided, just like PHP's password_hash()
        hashed_pw = make_password(password) if password else None

        Agent.objects.create(
            name=name, email=email, phone=phone, password_hash=hashed_pw
        )
        messages.success(request, f"Agent {name} added successfully.")
        return redirect("agent_list")

    return render(request, "billing/add_agent.html")


@login_required
@role_required(["Admin", "Editor"])
def edit_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    if request.method == "POST":
        agent.name = request.POST.get("name")
        agent.email = request.POST.get("email")
        agent.phone = request.POST.get("phone")
        agent.save()

        messages.success(request, "Agent updated successfully.")
        return redirect("agent_list")

    return render(request, "billing/edit_agent.html", {"agent": agent})


@login_required
@role_required(["Admin", "Editor"])
def delete_agent(request, agent_id):
    if request.method == "POST":
        agent = get_object_or_404(Agent, id=agent_id)
        agent.delete()
        messages.success(request, "Agent deleted successfully.")
    return redirect("agent_list")


@login_required
def view_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    from billing.models import Customer
    import re

    if request.method == "POST" and "setup_agent_login" in request.POST:
        username = request.POST.get("username", "").strip()
        temp_password = request.POST.get("password", "").strip()

        if not username:
            if agent.email:
                username = agent.email.split("@")[0].lower()
            else:
                username = re.sub(r"[^a-zA-Z0-9_]", "", agent.name.lower().replace(" ", "_"))

        if not temp_password:
            from billing.validators import generate_temp_password
            temp_password = generate_temp_password(10)
        else:
            from billing.validators import validate_password_policy
            from django.core.exceptions import ValidationError
            try:
                validate_password_policy(temp_password, identifier=username)
            except ValidationError as e:
                messages.error(request, str(e.message))
                return redirect("view_agent", agent_id=agent.id)

        # Check existing username conflicts
        existing_user = User.objects.filter(username__iexact=username).first()
        if existing_user and agent.user and existing_user != agent.user:
            messages.error(
                request,
                f"Username '{username}' is already taken by another account. Please pick a different username.",
            )
            return redirect("view_agent", agent_id=agent.id)
        elif existing_user and not agent.user:
            if hasattr(existing_user, "agent_profile"):
                messages.error(
                    request,
                    f"Username '{username}' is already linked to agent '{existing_user.agent_profile.name}'.",
                )
                return redirect("view_agent", agent_id=agent.id)
            if existing_user.is_staff or existing_user.is_superuser:
                messages.error(
                    request,
                    f"Username '{username}' belongs to a staff/admin user. Agents cannot use staff usernames.",
                )
                return redirect("view_agent", agent_id=agent.id)
            user = existing_user
        elif agent.user:
            user = agent.user
            user.username = username
        else:
            user = User(username=username)

        user.email = agent.email or ""
        user.first_name = agent.name[:30]
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.set_password(temp_password)
        user.save()

        agent.user = user
        agent.password_hash = user.password
        agent.save()

        try:
            SystemLog.objects.create(
                user=request.user.username if request.user.is_authenticated else "Staff",
                action=f"Configured Portal Login for Agent '{agent.name}' (Username: {username})",
                ip_address=request.META.get("REMOTE_ADDR", ""),
            )
        except Exception:
            pass

        # Store in session to display once on confirmation view without printing secrets to flash/logs
        request.session["agent_temp_credentials"] = {
            "agent_id": agent.id,
            "username": username,
            "temp_password": temp_password,
        }
        messages.success(
            request,
            f"Portal credentials saved for {agent.name}. Temporary credentials are displayed below.",
        )
        return redirect("view_agent", agent_id=agent.id)

    if request.method == "POST" and "toggle_agent_login" in request.POST:
        if agent.user:
            agent.user.is_active = not agent.user.is_active
            agent.user.save()
            status_str = "activated" if agent.user.is_active else "deactivated"
            messages.success(request, f"Agent portal account {status_str} for {agent.name}.")
        return redirect("view_agent", agent_id=agent.id)

    if request.method == "POST" and "update_referral" in request.POST:
        cust_id = request.POST.get("cust_id")
        referral_value = request.POST.get("referral_value")

        try:
            cust = Customer.objects.get(id=cust_id, agent=agent)
            if referral_value is not None:
                cust.referral_received = referral_value
            cust.adjusted_by_referral = (
                request.user.username if request.user.is_authenticated else "unknown"
            )
            cust.save()
            messages.success(
                request,
                f"Referral status updated for {cust.pppoe_username or cust.full_name}.",
            )
        except Customer.DoesNotExist:
            messages.error(request, "Customer not found.")

        return redirect("view_agent", agent_id=agent.id)

    customers = Customer.objects.filter(agent=agent)
    temp_credentials = request.session.pop("agent_temp_credentials", None)

    return render(
        request,
        "billing/view_agent.html",
        {"agent": agent, "customers": customers, "temp_credentials": temp_credentials},
    )


@login_required
def profile_view(request):
    return render(request, "billing/profile.html")


def unified_login_view(request):
    from billing.security import (
        get_client_ip,
        is_account_or_ip_locked,
        record_login_failure,
        clear_login_failures,
    )
    import re

    if request.user.is_authenticated:
        if hasattr(request.user, "agent_profile") and not request.user.is_staff:
            return redirect("agent_dashboard")
        return redirect("dashboard")
    if request.session.get("customer_id"):
        return redirect("customer_portal:portal_dashboard")

    if request.method == "POST":
        u = (request.POST.get("username") or "").strip()
        p = request.POST.get("password") or ""
        ip = get_client_ip(request)

        # Check account & IP lockout
        is_locked, remaining = is_account_or_ip_locked(u, ip)
        if is_locked:
            minutes = max(1, (remaining + 59) // 60)
            messages.error(
                request,
                f"Account or IP temporarily locked due to multiple failed login attempts. Please try again in {minutes} minute(s)."
            )
            return render(request, "billing/login.html")

        # 1. Try standard Admin/Staff/Agent login
        user = authenticate(request, username=u, password=p)
        if user is not None:
            clear_login_failures(u, ip)
            login(request, user)
            if hasattr(user, "agent_profile") and not user.is_staff:
                next_url = request.POST.get("next") or request.GET.get("next")
                return redirect(next_url if next_url else "agent_dashboard")
            next_url = request.POST.get("next") or request.GET.get("next")
            return redirect(next_url if next_url else "dashboard")

        # 2. Try Customer Login (username or phone ONLY; no full_name; check portal_password_hash)
        clean_digits = re.sub(r"\D", "", u)
        phone_candidates = [u]
        if clean_digits:
            phone_candidates.extend([
                clean_digits,
                "0" + clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits,
                "+63" + clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits,
                "63" + clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits,
            ])

        from django.db.models import Q
        customer = Customer.objects.filter(
            Q(pppoe_username__iexact=u) | Q(phone__in=phone_candidates)
        ).first()

        if customer and customer.check_portal_password(p):
            clear_login_failures(u, ip)

            # Check if temporary password expired (> 7 days)
            if customer.is_temp_password_expired():
                messages.error(
                    request,
                    "Your temporary password has expired (validity: 7 days). Please contact Gametech staff to reset your password."
                )
                return render(request, "billing/login.html")

            request.session["customer_id"] = customer.id
            request.session["customer_last_seen"] = timezone.now().isoformat()
            try:
                from django.core.cache import cache
                now = timezone.now()
                cache.set(f"seen_customer_{customer.id}", now, 300)
                active = cache.get("active_portal_customers") or {}
                active[str(customer.id)] = now.isoformat()
                cache.set("active_portal_customers", active, 600)
            except Exception:
                pass

            if customer.must_change_password:
                return redirect("customer_portal:force_change_password")

            next_url = request.POST.get("next") or request.GET.get("next")
            return redirect(
                next_url if next_url else "customer_portal:portal_dashboard"
            )

        # Neither matched: record failure and increment counter
        is_now_locked, attempts, lock_dur = record_login_failure(u, ip)
        if is_now_locked:
            messages.error(
                request,
                "Account has been locked for 15 minutes due to 5 consecutive failed login attempts."
            )
        else:
            remaining_attempts = max(1, 5 - attempts)
            messages.error(
                request,
                f"Invalid credentials. ({remaining_attempts} attempt{'s' if remaining_attempts != 1 else ''} remaining before lockout)"
            )

    return render(request, "billing/login.html")


@login_required
def profile_view(request):
    return render(request, "billing/profile.html")


@login_required
def online_staff_api(request):
    from django.core.cache import cache
    from django.contrib.auth.models import User
    from django.utils import timezone
    from billing.models import Customer

    now = timezone.now()

    # 1. Staff users
    staff_users = User.objects.all()
    staff_data = []
    for u in staff_users:
        last_seen = cache.get(f"seen_user_{u.id}")
        if last_seen:
            if isinstance(last_seen, str):
                from django.utils.dateparse import parse_datetime
                parsed = parse_datetime(last_seen)
                if parsed:
                    last_seen = parsed
                else:
                    last_seen = None

            if last_seen and getattr(last_seen, 'tzinfo', None) is None:
                last_seen = timezone.make_aware(last_seen)

            if last_seen and (now - last_seen).total_seconds() < 300:
                role = getattr(u, "role", "Staff")
                staff_data.append({"username": u.username, "role": role})

    # 2. Customer portal users
    active_customer_ids = set()
    active_customers_cache = cache.get("active_portal_customers") or {}
    cleaned_active_customers = {}

    for cid_str, ts_str in list(active_customers_cache.items()):
        try:
            # Check individual seen key: if deleted on logout or expired, skip
            last_seen = cache.get(f"seen_customer_{cid_str}")
            if last_seen is None:
                continue

            from django.utils.dateparse import parse_datetime
            ts = parse_datetime(ts_str) if isinstance(ts_str, str) else ts_str
            if ts and getattr(ts, 'tzinfo', None) is None:
                ts = timezone.make_aware(ts)
            if ts and (now - ts).total_seconds() < 300:
                active_customer_ids.add(int(cid_str))
                cleaned_active_customers[str(cid_str)] = ts_str
        except Exception:
            pass

    # Prune inactive/logged-out customers from cache
    if len(cleaned_active_customers) != len(active_customers_cache):
        cache.set("active_portal_customers", cleaned_active_customers, 600)

    # Compliment with database sessions ONLY if actively verified via cache (not logged out)
    try:
        from django.contrib.sessions.models import Session
        unexpired_sessions = Session.objects.filter(expire_date__gte=now)[:50]
        for s in unexpired_sessions:
            try:
                s_data = s.get_decoded()
                cid = s_data.get("customer_id")
                if cid:
                    # Must verify that this customer has not logged out and is active within 300s!
                    cust_seen = cache.get(f"seen_customer_{cid}")
                    if cust_seen is not None:
                        active_customer_ids.add(int(cid))
            except Exception:
                pass
    except Exception:
        pass

    customer_data = []
    if active_customer_ids:
        customers = Customer.objects.filter(id__in=active_customer_ids).select_related("plan")
        for c in customers:
            customer_data.append({
                "id": c.id,
                "name": c.full_name or c.pppoe_username,
                "username": c.pppoe_username or "",
                "plan": c.plan.name if c.plan else "",
                "status": c.status or "active",
            })

    total_count = len(staff_data) + len(customer_data)

    return JsonResponse({
        "status": "success",
        "data": staff_data,
        "staff": staff_data,
        "customers": customer_data,
        "staff_count": len(staff_data),
        "customer_count": len(customer_data),
        "total_count": total_count,
    })


def custom_logout_view(request):
    customer_id = request.session.get("customer_id")
    if customer_id:
        try:
            from django.core.cache import cache
            cache.delete(f"seen_customer_{customer_id}")
            active = cache.get("active_portal_customers") or {}
            active.pop(str(customer_id), None)
            active.pop(int(customer_id), None)
            cache.set("active_portal_customers", active, 600)
        except Exception:
            pass
        try:
            from django.contrib.sessions.models import Session
            for s in Session.objects.filter(expire_date__gte=timezone.now()):
                try:
                    s_data = s.get_decoded()
                    if str(s_data.get("customer_id")) == str(customer_id):
                        s.delete()
                except Exception:
                    pass
        except Exception:
            pass

    if request.user.is_authenticated:
        try:
            from django.core.cache import cache
            cache.delete(f"seen_user_{request.user.id}")
        except Exception:
            pass

    # Flush any unconsumed internal session messages so operational notices don't bleed into the login screen
    try:
        from django.contrib.messages import get_messages
        storage = get_messages(request)
        for _ in storage:
            pass
        storage.used = True
        storage._queued_messages = []
    except Exception:
        pass

    logout(request)
    return redirect("login")

