from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from billing.decorators import role_required
from django.contrib import messages
from django.http import JsonResponse
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI

@login_required
def nap_list_view(request):
    from network_manager.models import NapBox
    naps = NapBox.objects.all().order_by('-created_at')
    return render(request, 'network_manager/nap_list.html', {'naps': naps})

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def add_nap_view(request):
    from network_manager.models import NapBox
    if request.method == 'POST':
        napbox_no = request.POST.get('napbox_no')
        nap_latitude = request.POST.get('nap_latitude')
        nap_longitude = request.POST.get('nap_longitude')
        marker_color = request.POST.get('marker_color', 'red')
        NapBox.objects.create(
            napbox_no=napbox_no,
            latitude=nap_latitude if nap_latitude else None,
            longitude=nap_longitude if nap_longitude else None,
            marker_color=marker_color
        )
        messages.success(request, 'NAP Box mapping saved successfully.')
        return redirect('nap_list')
    return render(request, 'network_manager/nap_form.html')

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def edit_nap_view(request, nap_id):
    from network_manager.models import NapBox
    nap = get_object_or_404(NapBox, id=nap_id)
    if request.method == 'POST':
        nap.napbox_no = request.POST.get('napbox_no')
        nap_latitude = request.POST.get('nap_latitude')
        nap_longitude = request.POST.get('nap_longitude')
        if nap_latitude:
            nap.latitude = nap_latitude
        if nap_longitude:
            nap.longitude = nap_longitude
        nap.marker_color = request.POST.get('marker_color', 'red')
        nap.save()
        messages.success(request, 'NAP Box mapping updated successfully.')
        return redirect('nap_list')
    return render(request, 'network_manager/nap_form.html', {'nap': nap})

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def delete_nap_view(request, nap_id):
    from network_manager.models import NapBox
    if request.method == 'POST':
        nap = get_object_or_404(NapBox, id=nap_id)
        nap.delete()
        messages.success(request, 'NAP Box deleted successfully.')
    return redirect('nap_list')

