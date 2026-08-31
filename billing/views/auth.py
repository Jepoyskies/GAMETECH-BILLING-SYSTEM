from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
import os
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.views.decorators.http import require_POST
from ..decorators import role_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, Max
from django.core.paginator import Paginator
import json
from datetime import timedelta, datetime
from ..models import (
    SystemAdmin, SubscriptionPlan, Agent, AccountType,
    Customer, Barangay, Payment, Rebate, SystemLog, SmsLog, CignalPlay, AuditLog, AddOnRequest, Notification, ImprovementRequest
)
import requests
from network_manager.models import MikrotikDevice, NapBox
from network_manager.services import MikrotikAPI
from django.db import transaction
import calendar

def agent_list(request):
    agents = Agent.objects.all().order_by('name')
    return render(request, 'billing/agents.html', {'agents': agents})


@login_required
@role_required(['Admin', 'Editor'])
def add_agent(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')

        # Hash password if provided, just like PHP's password_hash()
        hashed_pw = make_password(password) if password else None

        Agent.objects.create(name=name, email=email,
                             phone=phone, password_hash=hashed_pw)
        messages.success(request, f"Agent {name} added successfully.")
        return redirect('agent_list')

    return render(request, 'billing/add_agent.html')


@login_required
@role_required(['Admin', 'Editor'])
def edit_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    if request.method == 'POST':
        agent.name = request.POST.get('name')
        agent.email = request.POST.get('email')
        agent.phone = request.POST.get('phone')
        agent.save()

        messages.success(request, "Agent updated successfully.")
        return redirect('agent_list')

    return render(request, 'billing/edit_agent.html', {'agent': agent})


@login_required
@role_required(['Admin', 'Editor'])
def delete_agent(request, agent_id):
    if request.method == 'POST':
        agent = get_object_or_404(Agent, id=agent_id)
        agent.delete()
        messages.success(request, "Agent deleted successfully.")
    return redirect('agent_list')


def view_agent(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    from ..models import Customer

    if request.method == 'POST' and 'update_referral' in request.POST:
        cust_id = request.POST.get('cust_id')
        referral_value = request.POST.get('referral_value')

        try:
            cust = Customer.objects.get(id=cust_id, agent=agent)
            if referral_value is not None:
                cust.referral_received = referral_value
            cust.adjusted_by_referral = request.user.username if request.user.is_authenticated else 'unknown'
            cust.save()
            messages.success(
                request, f"Referral status updated for {cust.pppoe_username or cust.full_name}.")
        except Customer.DoesNotExist:
            messages.error(request, "Customer not found.")

        return redirect('view_agent', agent_id=agent.id)

    customers = Customer.objects.filter(agent=agent)

    return render(request, 'billing/view_agent.html', {'agent': agent, 'customers': customers})


@login_required
def staff_list(request):
    # Auto-sync any Django Users (like hidden superusers created via CLI) to SystemAdmin
    from django.contrib.auth.models import User
    from django.db.models import Q
    for u in User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)):
        sys_admin, created = SystemAdmin.objects.get_or_create(
            username=u.username,
            defaults={
                'full_name': f"{u.first_name} {u.last_name}".strip() or u.username,
                'email': u.email or f"{u.username}@example.com",
                'role': 'Admin' if u.is_superuser else 'Viewer',
                'status': 'Active' if u.is_active else 'Inactive',
                'password_hash': 'managed_by_django'
            }
        )
        if not created and u.is_superuser and sys_admin.role != 'Admin':
            sys_admin.role = 'Admin'
            sys_admin.save(update_fields=['role'])

    # Fetch all admins, ordered by the newest created
    staff_members = SystemAdmin.objects.all().order_by('-created_at')
    return render(request, 'billing/staff_and_admins.html', {'staff_members': staff_members})


@role_required(['Admin'])
@login_required
def add_staff(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        role = request.POST.get('role')
        status = request.POST.get('status')
        raw_password = request.POST.get('password')

        # Check if username or email already exists to prevent errors
        if User.objects.filter(username=username).exists() or SystemAdmin.objects.filter(username=username).exists():
            messages.error(request, "That username is already taken.")
            return redirect('add_staff')

        if User.objects.filter(email=email).exists() or SystemAdmin.objects.filter(email=email).exists():
            messages.error(request, "That email is already registered.")
            return redirect('add_staff')

        try:
            with transaction.atomic():
                # 1. Create the Django User (handles password hashing securely)
                user = User(
                    username=username,
                    email=email,
                    is_staff=True,  # Allows login to /admin/
                    is_active=(status == 'Active')
                )
                if role == 'Admin':
                    user.is_superuser = True
                user.set_password(raw_password)
                user.save() # This also triggers the signal to create EmployeeProfile

                # 2. Assign User to the correct RBAC Group
                from django.contrib.auth.models import Group
                group = Group.objects.filter(name=role).first()
                if group:
                    user.groups.add(group)

                # 3. Create the legacy SystemAdmin record for UI compatibility
                SystemAdmin.objects.create(
                    username=username,
                    full_name=full_name,
                    email=email,
                    role=role,
                    status=status,
                    password_hash=user.password
                )

            messages.success(request, f"Staff member '{full_name}' added successfully!")
            return redirect('staff_list')
        except Exception as e:
            messages.error(request, f"Error creating staff member: {str(e)}")
            return redirect('add_staff')

    return render(request, 'billing/add_staff.html')


@role_required(['Admin'])
@login_required
def edit_staff(request, pk):
    # Retrieve user role safely (fallback to Viewer to be safe)
    user_role = getattr(request.user, 'role', 'Viewer')
    
    # Strictly prohibit Viewers
    if user_role == 'Viewer':
        messages.error(request, "Access denied. Viewers are not permitted to edit staff details.")
        return redirect('staff_list')

    staff = get_object_or_404(SystemAdmin, pk=pk)
    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        role = request.POST.get('role')
        status = request.POST.get('status')
        raw_password = request.POST.get('password')

        # Check if username or email already exists to prevent errors
        if User.objects.filter(username=username).exclude(username=staff.username).exists() or \
           SystemAdmin.objects.filter(username=username).exclude(pk=pk).exists():
            messages.error(request, "That username is already taken.")
            return redirect('edit_staff', pk=pk)

        if User.objects.filter(email=email).exclude(email=staff.email).exists() or \
           SystemAdmin.objects.filter(email=email).exclude(pk=pk).exists():
            messages.error(request, "That email is already registered.")
            return redirect('edit_staff', pk=pk)

        try:
            with transaction.atomic():
                # Update or Create underlying Django User
                user = User.objects.filter(username=staff.username).first()
                if not user:
                    user = User(
                        username=username,
                        email=email,
                        is_staff=True,
                        is_active=(status == 'Active'),
                        is_superuser=(role == 'Admin')
                    )
                    if raw_password:
                        user.set_password(raw_password)
                    else:
                        user.set_unusable_password()
                    user.save()
                else:
                    user.username = username
                    user.email = email
                    user.is_active = (status == 'Active')
                    user.is_superuser = (role == 'Admin')
                    
                    if user_role == 'Admin' and raw_password:
                        user.set_password(raw_password)
                    
                    user.save()
                    
                # Update Group assignment
                user.groups.clear()
                from django.contrib.auth.models import Group
                group = Group.objects.filter(name=role).first()
                if group:
                    user.groups.add(group)

                # Update legacy staff user
                staff.username = username
                staff.full_name = full_name
                staff.email = email
                staff.role = role
                staff.status = status

                # Admins only: Override password if one is provided (for legacy compatibility)
                if user_role == 'Admin' and raw_password:
                    if user:
                        staff.password_hash = user.password
                    else:
                        staff.password_hash = make_password(raw_password)

                staff.save()

            messages.success(request, f"Staff member '{full_name}' updated successfully!")
            return redirect('staff_list')
        except Exception as e:
            messages.error(request, f"Error updating staff member: {str(e)}")
            return redirect('edit_staff', pk=pk)

    return render(request, 'billing/edit_staff.html', {'staff': staff})


@login_required
def profile_view(request):
    return render(request, 'billing/profile.html')


def unified_login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.session.get('customer_id'):
        return redirect('customer_portal:portal_dashboard')

    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        # 1. Try standard Admin/Staff login
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url if next_url else 'dashboard')
            
        # 2. Try Customer Login
        try:
            from django.db.models import Q
            customer = Customer.objects.filter(
                Q(full_name__iexact=u, portal_password=p) | 
                Q(phone=u, portal_password=p)
            ).first()
            
            if customer:
                request.session['customer_id'] = customer.id
                next_url = request.POST.get('next') or request.GET.get('next')
                return redirect(next_url if next_url else 'customer_portal:portal_dashboard')
            else:
                messages.error(request, 'Invalid username or password.')

        except Customer.DoesNotExist:
            messages.error(request, 'Invalid username or password.')
            
    return render(request, 'billing/login.html')


@login_required
def online_staff_api(request):
    from django.core.cache import cache
    from django.contrib.auth.models import User
    
    # We only check users who could be staff (all User models typically in this app)
    # This might be <20 users, so iterating over them and checking cache is fast enough.
    staff_users = User.objects.all()
    
    data = []
    for u in staff_users:
        # The ActiveUserMiddleware sets this cache key for 5 minutes when a user is active
        if cache.get(f'seen_user_{u.id}'):
            role = getattr(u, 'role', 'Staff')
            data.append({
                'username': u.username,
                'role': role
            })
        
    return JsonResponse({'status': 'success', 'data': data})


