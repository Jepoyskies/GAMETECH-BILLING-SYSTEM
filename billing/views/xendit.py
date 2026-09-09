import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from billing.models import Customer, Payment

# IMPORTANT: You will need to install xendit-python later
# pip install xendit-python

@login_required
def create_xendit_invoice(request, customer_id):
    """
    Stub for creating a Xendit Invoice.
    This will be called when a customer clicks 'Pay via GCash/Maya' on their portal.
    """
    if request.method == 'POST':
        # customer = Customer.objects.get(id=customer_id)
        # 1. Initialize Xendit API Client using your Secret Key
        # 2. Build Invoice request (Amount, Payer Email, Description)
        # 3. Call xendit API to generate invoice URL
        # 4. Return invoice URL as JSON response so the frontend can redirect the user
        
        return JsonResponse({"status": "pending", "message": "Xendit integration is being prepared. Waiting for API Keys."})
    return JsonResponse({"error": "Invalid request method."}, status=400)


@csrf_exempt
def xendit_webhook(request):
    """
    Webhook listener for Xendit. 
    Xendit will POST to this URL automatically when a payment succeeds.
    """
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            # 1. Verify Callback Token from Xendit to ensure authenticity
            # 2. Check if payload['status'] == 'PAID'
            # 3. Find the corresponding Customer / Invoice ID
            # 4. Create a PaymentLog entry
            # 5. Automatically call network_manager.services to unsuspend the Mikrotik profile
            
            # For now, just log and return 200 OK so Xendit knows we received it
            print("Received Xendit Webhook:", payload)
            
            return JsonResponse({"message": "Webhook received"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    return JsonResponse({"error": "Invalid request method."}, status=400)
