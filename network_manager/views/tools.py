from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from billing.decorators import role_required
from django.contrib import messages
from django.http import JsonResponse
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

@login_required
def fbt_plc_calculator_view(request):
    """
    Renders the standalone Fiber Network (FBT/PLC) Calculator tool.
    No database context required.
    """
    return render(request, 'network_manager/fbt_plc_calculator.html')

