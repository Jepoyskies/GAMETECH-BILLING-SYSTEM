from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import DispatchRecord, MonitoringRecord, JobDetail, ConfigOption, Technician, Team
from .forms import MonitoringRecordForm, DispatchRecordForm
from django.contrib import messages
from django.utils import timezone

@login_required
def dashboard_view(request):
    return render(request, 'dispatch/dashboard.html')

@login_required
def dispatch_monitoring_view(request):
    if request.method == 'POST':
        form = DispatchRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.csr = request.user
            record.save()
            form.save_m2m() # Save teams
            messages.success(request, 'Dispatch record added successfully!')
            return redirect('dispatch_monitoring')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DispatchRecordForm(initial={'date': timezone.now().date()})
    
    records = DispatchRecord.objects.all().order_by('-date')
    return render(request, 'dispatch/dispatch_monitoring.html', {'records': records, 'form': form})

def _handle_monitoring_view(request, tab_type, template_name):
    if request.method == 'POST':
        form = MonitoringRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.tab_type = tab_type
            record.csr = request.user
            record.save()
            form.save_m2m() # Save teams
            messages.success(request, 'Record added successfully!')
            return redirect(request.path)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = MonitoringRecordForm(initial={'tab_type': tab_type, 'date': timezone.now().date()})
    
    records = MonitoringRecord.objects.filter(tab_type=tab_type).order_by('-date')
    return render(request, template_name, {'records': records, 'form': form})

@login_required
def internet_install_view(request):
    return _handle_monitoring_view(request, 'INTERNET_INSTALL', 'dispatch/internet_install.html')

@login_required
def cignal_install_view(request):
    return _handle_monitoring_view(request, 'CIGNAL_PLAY', 'dispatch/cignal_install.html')

@login_required
def client_concerns_view(request):
    return _handle_monitoring_view(request, 'CLIENT_CONCERNS', 'dispatch/client_concerns.html')

@login_required
def complete_job_view(request, record_id):
    from .forms import JobDetailForm
    record = get_object_or_404(MonitoringRecord, id=record_id)
    
    # Get or create JobDetail for this record
    job_detail, created = JobDetail.objects.get_or_create(record=record)
    
    if request.method == 'POST':
        form = JobDetailForm(request.POST, instance=job_detail)
        if form.is_valid():
            form.save()
            # Also update status to 'Done' if there's a done option
            done_option = ConfigOption.objects.filter(module='MONITORING', list_type='STATUS', label__icontains='Done').first()
            if done_option:
                record.status_option = done_option
                record.save()
            messages.success(request, 'Job details saved and marked as Done.')
            
            # Redirect back to the correct tab
            if record.tab_type == 'INTERNET_INSTALL':
                return redirect('internet_install')
            elif record.tab_type == 'CIGNAL_PLAY':
                return redirect('cignal_install')
            else:
                return redirect('client_concerns')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = JobDetailForm(instance=job_detail)
        
    return render(request, 'dispatch/complete_job.html', {'form': form, 'record': record})

