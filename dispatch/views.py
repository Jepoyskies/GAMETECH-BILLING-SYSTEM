from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import DispatchRecord, MonitoringRecord, JobDetail, ConfigOption, Technician, Team
from django.contrib import messages

@login_required
def dashboard_view(request):
    return render(request, 'dispatch/dashboard.html')

@login_required
def dispatch_monitoring_view(request):
    records = DispatchRecord.objects.all().order_by('-date')
    return render(request, 'dispatch/dispatch_monitoring.html', {'records': records})

@login_required
def internet_install_view(request):
    records = MonitoringRecord.objects.filter(tab_type='INTERNET_INSTALL').order_by('-date')
    return render(request, 'dispatch/internet_install.html', {'records': records})

@login_required
def cignal_install_view(request):
    records = MonitoringRecord.objects.filter(tab_type='CIGNAL_PLAY').order_by('-date')
    return render(request, 'dispatch/cignal_install.html', {'records': records})

@login_required
def client_concerns_view(request):
    records = MonitoringRecord.objects.filter(tab_type='CLIENT_CONCERNS').order_by('-date')
    return render(request, 'dispatch/client_concerns.html', {'records': records})
