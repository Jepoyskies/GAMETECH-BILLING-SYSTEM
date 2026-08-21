
@login_required
def payment_receipt_view(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    customer = payment.customer

    # Check if the payment action type is a standard renewal, upgrade, downgrade, rebate, etc.
    # The Payment model has an 'action' field or 'reason', but wait, the action_type in payment_success 
    # was hardcoded in pay_customer_view based on the logic. 
    # Let's reconstruct it.
    action_type = payment.reason or 'Standard Renewal'

    # Reconstruct Messenger Template
    messenger_msg = f""Hi {customer.full_name if customer else payment.username},

Thank you for your payment of P{payment.amount} via {payment.payment_method}. Your internet connection is now active until {payment.new_expiry.strftime('%B %d, %Y') if hasattr(payment, 'new_expiry') and payment.new_expiry else payment.expires_at.strftime('%B %d, %Y') if payment.expires_at else 'N/A'}.""

    if 'Upgrade' in action_type:
        messenger_msg += f""

Thank you for upgrading! Enjoy your faster speeds.""
    elif 'Downgrade' in action_type:
        messenger_msg += f""

Your plan has been successfully updated. If you wish to upgrade soon for faster speeds, you can always let us know!""

    context = {
        'customer': customer,
        'new_expiry': payment.expires_at.strftime('%Y-%m-%d %H:%M:%S') if payment.expires_at else 'N/A',
        'adjusted_by': payment.adjusted_by if hasattr(payment, 'adjusted_by') else request.user.username,
        'action_type': action_type,
        'amount': payment.amount,
        'messenger_template': messenger_msg,
        'next_url': request.META.get('HTTP_REFERER') or reverse('customer_list')
    }
    return render(request, 'billing/payment_success.html', context)
