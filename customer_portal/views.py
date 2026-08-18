from django.shortcuts import render, redirect
from django.contrib import messages
from billing.models import Customer, Payment

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
            return redirect('customer_portal:portal_dashboard')
        except Customer.DoesNotExist:
            messages.error(request, 'Invalid PPPoE username or password.')
            
    return render(request, 'customer_portal/portal_login.html')

def portal_dashboard(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('customer_portal:portal_login')
        
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect('customer_portal:portal_login')
        
    plan = customer.plan
    payments = Payment.objects.filter(customer=customer).order_by('-created_at')[:10]
    
    context = {
        'customer': customer,
        'plan': plan,
        'payments': payments,
    }
    return render(request, 'customer_portal/portal_dashboard.html', context)

def portal_logout(request):
    request.session.flush()
    return redirect('customer_portal:portal_login')
