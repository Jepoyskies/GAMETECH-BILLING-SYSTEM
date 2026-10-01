"""Resolve customers flagged by the legacy import, from the import page.

Sir Rom's rule: never remove a customer. The old PHP system is the source of
truth, so an archived record keeps every field and can be brought back with one
click. "Archive" sets status='inactive' -- it never deletes a row.
"""

import json

from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from billing.models import Customer, SystemLog

# Hard delete is deliberately not offered. Archiving is reversible.
ACTIONS = {"archive", "activate", "set_expiry", "clear_expiry"}


def _log(user, action, customer, old, new):
    SystemLog.objects.create(
        table_name="Customer",
        record_id=str(customer.id),
        action=action.upper(),
        changed_by=getattr(user, "username", "unknown"),
        target_name=customer.full_name,
        old_data=json.dumps(old, default=str),
        new_data=json.dumps(new, default=str),
    )


def handle_issue_action(request):
    """Apply a review decision. Returns a (redirect, message) pair.

    Everything is wrapped in one transaction and written to SystemLog, so the
    decision is both atomic and auditable.
    """
    action = request.POST.get("issue_action", "")
    if action not in ACTIONS:
        return None, None

    ids = [i for i in request.POST.getlist("customer_ids") if i.isdigit()]
    if not ids:
        return None, ("Pick at least one customer first.", "warning")

    qs = Customer.objects.filter(id__in=ids)
    count = 0
    try:
        with transaction.atomic():
            for customer in qs:
                old = {
                    "status": customer.status,
                    "expires_at": str(customer.expires_at) if customer.expires_at else None,
                }
                if action == "archive":
                    customer.status = "inactive"
                    customer.save(update_fields=["status"])
                elif action == "activate":
                    customer.status = "active"
                    customer.save(update_fields=["status"])
                elif action == "set_expiry":
                    raw = request.POST.get("expires_at", "").strip()
                    parsed = parse_datetime(raw) if raw else None
                    if parsed is None and raw:
                        return None, (f"'{raw}' is not a valid date and time.", "error")
                    if parsed is not None and timezone.is_naive(parsed):
                        parsed = timezone.make_aware(parsed)
                    customer.expires_at = parsed
                    customer.save(update_fields=["expires_at"])
                elif action == "clear_expiry":
                    customer.expires_at = None
                    customer.save(update_fields=["expires_at"])

                new = {
                    "status": customer.status,
                    "expires_at": str(customer.expires_at) if customer.expires_at else None,
                }
                _log(request.user, f"issue_{action}", customer, old, new)
                count += 1
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator
        return None, (f"Could not apply that change: {exc}", "error")

    if action == "archive":
        msg = (
            f"Archived {count} customer(s). Nothing was deleted -- they are now "
            f"inactive and can be reactivated any time."
        )
    elif action == "activate":
        msg = f"Reactivated {count} customer(s)."
    elif action == "set_expiry":
        msg = f"Set the expiration date on {count} customer(s)."
    else:
        msg = (
            f"Cleared the expiration date on {count} customer(s). They will show "
            f"under 'No expiration date' again until a date is set."
        )
    return count, (msg, "success")
