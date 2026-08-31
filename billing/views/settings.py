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

@login_required
def settings_view(request):
    return render(request, 'billing/settings.html')


@role_required(['Admin'])
@login_required
def admin_panel_view(request):
    user_role = getattr(request.user, 'role', 'Viewer')
    if user_role != 'Admin':
        messages.error(request, "Access denied. Only Admins can access the Admin Panel.")
        return redirect('dashboard')
        
    return render(request, 'billing/admin_panel.html')


@login_required
def system_logs_view(request):
    logs = SystemLog.objects.all()

    # Search filter
    search_query = request.GET.get('search', '').strip()
    if search_query:
        logs = logs.filter(
            Q(table_name__icontains=search_query) |
            Q(changed_by__icontains=search_query) |
            Q(action__icontains=search_query) |
            Q(old_data__icontains=search_query) |
            Q(new_data__icontains=search_query)
        )

    # Action filter
    action_filter = request.GET.get('action_filter', '').strip().upper()
    if action_filter == 'ADD':
        logs = logs.filter(action__iexact='ADD')
    elif action_filter == 'UPDATE':
        logs = logs.filter(action__iexact='UPDATE')
    elif action_filter == 'DELETE':
        logs = logs.filter(action__iexact='DELETE')

    # Date filter
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    if date_from:
        logs = logs.filter(changed_at__gte=f"{date_from} 00:00:00")
    if date_to:
        logs = logs.filter(changed_at__lte=f"{date_to} 23:59:59")

    # Sorting
    sort_column = request.GET.get('sort', 'changed_at')
    sort_dir = request.GET.get('dir', 'desc').lower()
    
    allowed_sort_columns = ['changed_at', 'table_name', 'record_id', 'action', 'changed_by']
    if sort_column not in allowed_sort_columns:
        sort_column = 'changed_at'
        
    order_prefix = '-' if sort_dir == 'desc' else ''
    logs = logs.order_by(f"{order_prefix}{sort_column}")

    # Pagination
    paginator = Paginator(logs, 10)  # 10 logs per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Dynamically resolve target names based on table_name
    from ..models import Customer, Payment, AddOnRequest, SubscriptionPlan, Agent, SystemAdmin, Barangay, AccountType
    from network_manager.models import MikrotikDevice, NapBox

    # Initialize all targets to None
    for log in page_obj:
        log.target_customer = None
        log.target_icon = "fas fa-cube" # default icon

    # Group record IDs by table
    from collections import defaultdict
    table_ids = defaultdict(list)
    for log in page_obj:
        if str(log.record_id).isdigit(): # ensure it's a valid PK
            table_ids[log.table_name].append(log.record_id)
        
    # Bulk fetch names
    resolved_names = defaultdict(dict)
    
    if 'Customer' in table_ids:
        qs = Customer.objects.filter(id__in=table_ids['Customer']).values('id', 'full_name')
        resolved_names['Customer'] = {str(c['id']): (c['full_name'], 'fas fa-user') for c in qs}
        
    if 'Payment' in table_ids:
        qs = Payment.objects.filter(id__in=table_ids['Payment']).select_related('customer').values('id', 'customer__full_name')
        resolved_names['Payment'] = {str(p['id']): (p['customer__full_name'] or 'Unknown', 'fas fa-user-circle') for p in qs}
        
    if 'AddOnRequest' in table_ids:
        qs = AddOnRequest.objects.filter(id__in=table_ids['AddOnRequest']).select_related('customer').values('id', 'customer__full_name')
        resolved_names['AddOnRequest'] = {str(a['id']): (a['customer__full_name'] or 'Unknown', 'fas fa-plus-circle') for a in qs}
        
    if 'MikrotikDevice' in table_ids:
        qs = MikrotikDevice.objects.filter(id__in=table_ids['MikrotikDevice']).values('id', 'device_name')
        resolved_names['MikrotikDevice'] = {str(m['id']): (m['device_name'], 'fas fa-server') for m in qs}
        
    if 'NapBox' in table_ids:
        qs = NapBox.objects.filter(id__in=table_ids['NapBox']).values('id', 'napbox_no')
        resolved_names['NapBox'] = {str(n['id']): (n['napbox_no'], 'fas fa-box') for n in qs}
        
    if 'SubscriptionPlan' in table_ids:
        qs = SubscriptionPlan.objects.filter(id__in=table_ids['SubscriptionPlan']).values('id', 'name')
        resolved_names['SubscriptionPlan'] = {str(s['id']): (s['name'], 'fas fa-wifi') for s in qs}
        
    if 'Agent' in table_ids:
        qs = Agent.objects.filter(id__in=table_ids['Agent']).values('id', 'name')
        resolved_names['Agent'] = {str(a['id']): (a['name'], 'fas fa-user-tie') for a in qs}
        
    if 'SystemAdmin' in table_ids:
        qs = SystemAdmin.objects.filter(id__in=table_ids['SystemAdmin']).values('id', 'username')
        resolved_names['SystemAdmin'] = {str(s['id']): (s['username'], 'fas fa-user-shield') for s in qs}
        
    if 'Barangay' in table_ids:
        qs = Barangay.objects.filter(id__in=table_ids['Barangay']).values('id', 'name')
        resolved_names['Barangay'] = {str(b['id']): (b['name'], 'fas fa-map-marker-alt') for b in qs}
        
    if 'AccountType' in table_ids:
        qs = AccountType.objects.filter(id__in=table_ids['AccountType']).values('id', 'type_name')
        resolved_names['AccountType'] = {str(a['id']): (a['type_name'], 'fas fa-tags') for a in qs}

    # Attach to logs
    for log in page_obj:
        name = None
        icon = None
        
        # Prefer the new target_name field in the model if it exists
        if hasattr(log, 'target_name') and log.target_name:
            name = log.target_name
            # Still determine the icon based on table_name
            if log.table_name == 'Customer': icon = 'fas fa-user'
            elif log.table_name == 'Payment': icon = 'fas fa-user-circle'
            elif log.table_name == 'AddOnRequest': icon = 'fas fa-plus-circle'
            elif log.table_name == 'MikrotikDevice': icon = 'fas fa-server'
            elif log.table_name == 'NapBox': icon = 'fas fa-box'
            elif log.table_name == 'SubscriptionPlan': icon = 'fas fa-wifi'
            elif log.table_name == 'Agent': icon = 'fas fa-user-tie'
            elif log.table_name == 'SystemAdmin': icon = 'fas fa-user-shield'
            elif log.table_name == 'Barangay': icon = 'fas fa-map-marker-alt'
            elif log.table_name == 'AccountType': icon = 'fas fa-tags'
            
        # Fallback to the DB lookup for older logs before the migration
        elif log.table_name in resolved_names:
            name, icon = resolved_names[log.table_name].get(str(log.record_id), (None, None))
            
        if name:
            log.target_customer = name
            log.target_icon = icon or "fas fa-cube"

    # Attach actor roles for the USER column
    admin_roles = dict(SystemAdmin.objects.values_list('username', 'role'))
    agent_names = set(Agent.objects.values_list('user__username', flat=True))
    
    for log in page_obj:
        user_str = log.changed_by or 'Unknown'
        if user_str.startswith('System/'):
            log.actor_role = 'System'
        elif user_str in admin_roles:
            log.actor_role = admin_roles[user_str]
        elif user_str in agent_names:
            log.actor_role = 'Agent'
        else:
            log.actor_role = 'User'

    # Reconstruct query string for pagination links
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    
    context = {
        'logs': page_obj,
        'search': search_query,
        'action_filter': action_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort_column,
        'dir': sort_dir,
        'query_params': query_params.urlencode(),
        'page_range': page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
    }
    return render(request, 'billing/logs.html', context)


@login_required
def account_type_list(request):
    account_types = AccountType.objects.all().order_by('type_name')
    return render(request, 'billing/settings_list.html', {
        'items': account_types,
        'title': 'Manage Account Types',
        'item_name': 'Account Type',
        'create_url': 'create_account_type',
        'edit_url_name': 'edit_account_type',
        'delete_url_name': 'delete_account_type',
    })


@login_required
def create_account_type(request):
    if request.method == 'POST':
        form = AccountTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account Type created successfully!")
            return redirect('account_type_list')
    else:
        form = AccountTypeForm()
    return render(request, 'billing/settings_form.html', {'form': form, 'title': 'Create Account Type', 'back_url': 'account_type_list'})


@role_required(['Admin', 'Editor'])
@login_required
def edit_account_type(request, pk):
    obj = get_object_or_404(AccountType, pk=pk)
    if request.method == 'POST':
        form = AccountTypeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Account Type updated successfully!")
            return redirect('account_type_list')
    else:
        form = AccountTypeForm(instance=obj)
    return render(request, 'billing/settings_form.html', {'form': form, 'title': 'Edit Account Type', 'back_url': 'account_type_list'})


@role_required(['Admin', 'Editor'])
@login_required
def delete_account_type(request, pk):
    obj = get_object_or_404(AccountType, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, "Account Type deleted successfully!")
    return redirect('account_type_list')


@login_required
def barangay_list(request):
    barangays = Barangay.objects.all().order_by('name')
    return render(request, 'billing/settings_list.html', {
        'items': barangays,
        'title': 'Manage Barangays',
        'item_name': 'Barangay',
        'create_url': 'create_barangay',
        'edit_url_name': 'edit_barangay',
        'delete_url_name': 'delete_barangay',
    })


@login_required
def create_barangay(request):
    if request.method == 'POST':
        form = BarangayForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Barangay created successfully!")
            return redirect('barangay_list')
    else:
        form = BarangayForm()
    return render(request, 'billing/settings_form.html', {'form': form, 'title': 'Create Barangay', 'back_url': 'barangay_list'})


@login_required
def edit_barangay(request, pk):
    obj = get_object_or_404(Barangay, pk=pk)
    if request.method == 'POST':
        form = BarangayForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Barangay updated successfully!")
            return redirect('barangay_list')
    else:
        form = BarangayForm(instance=obj)
    return render(request, 'billing/settings_form.html', {'form': form, 'title': 'Edit Barangay', 'back_url': 'barangay_list'})


@login_required
def delete_barangay(request, pk):
    obj = get_object_or_404(Barangay, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, "Barangay deleted successfully!")
    return redirect('barangay_list')


@login_required
def backup_database_view(request):
    db_path = settings.DATABASES['default']['NAME']
    if os.path.exists(db_path):
        response = FileResponse(open(db_path, 'rb'), as_attachment=True, filename=f"gametech_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.sqlite3")
        return response
    
    messages.error(request, "Database file not found.")
    return redirect('settings')


@login_required
def submit_improvement_request(request):
    """AJAX endpoint to submit an improvement request from Sir Romnick."""
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            msg = data.get('message', '').strip()
            if not msg:
                return JsonResponse({'success': False, 'error': 'Message cannot be empty.'})
            ImprovementRequest.objects.create(
                submitted_by=request.user,
                message=msg,
            )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method.'})


@login_required
@role_required(['Admin'])
def improvement_requests_list(request):
    """Admin page to view all submitted improvement requests."""
    requests_qs = ImprovementRequest.objects.select_related('submitted_by').all()
    return render(request, 'billing/improvement_requests.html', {'improvement_requests': requests_qs})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def changelog_view(request):
    return render(request, 'billing/changelog.html')


@login_required
@role_required(['Admin'])
def import_legacy_data_view(request):
    import csv
    import io
    from django.contrib import messages
    from django.core.management import call_command
    from django.http import HttpResponseRedirect
    from django.urls import reverse

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Please upload a CSV file.")
            return HttpResponseRedirect(reverse('import_legacy_data'))

        if not csv_file.name.endswith('.csv'):
            messages.error(request, "File must be a CSV.")
            return HttpResponseRedirect(reverse('import_legacy_data'))

        try:
            # We save the file to a temp location so the management command can read it
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                for chunk in csv_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            # Run the migration command
            call_command('core_migration', tmp_path)
            messages.success(request, "Legacy data imported successfully!")
        except Exception as e:
            messages.error(request, f"Error during migration: {str(e)}")

        return HttpResponseRedirect(reverse('import_legacy_data'))

    return render(request, 'billing/import_data.html')


