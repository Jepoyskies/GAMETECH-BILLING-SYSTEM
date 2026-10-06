"""
Single source of truth for "may this person see subscriber billing data?".

The customer list was hardened first (see `_can_view_billing` in
`customers/list.py`) after a field Technician was found able to browse the whole
subscriber list -- names, addresses, phones, balances. That fix was local to one
view, so two other pages that expose the same class of data were missed:

  * /logs/payments/  -- every payment, with amounts and reference numbers
  * /sms/            -- a working SMS composer pre-filled with subscriber mobiles

Both carried `@login_required` and nothing else, so any authenticated account --
including a Technician and an Agent -- could open them.

This module exists so the rule is defined once. The StaffRole matrix
(`can_access_billing`) stays the authority: the Role Editor remains the single
place an administrator changes who can see billing, and these helpers just ask
it. Admin / Editor / CSR / Viewer are permitted; Agent, Technician and Dispatch
are not.
"""

from django.shortcuts import redirect
from django.contrib import messages


def can_access_billing(user):
    """True when this user may open subscriber/billing pages.

    Mirrors the rule the customer list already used. Kept deliberately
    fail-closed: if the role matrix cannot be read, the answer is no.
    """
    if user is None:
        return False
    if getattr(user, "is_superuser", False):
        return True
    perms = getattr(user, "role_perms", None)
    if perms is None:
        return False
    return bool(getattr(perms, "can_access_billing", False))


def require_billing_access(request, dest):
    """Redirect to `dest` unless the user may see billing data.

    Returns True when access is allowed, so a view can read:

        if not require_billing_access(request, "dashboard"):
            return redirect("dashboard")
    """
    if can_access_billing(request.user):
        return True

    messages.error(
        request,
        "Your role does not have access to billing data. Technicians and agents "
        "see only the jobs assigned to them.",
    )
    return False


def is_agent(user):
    """True for an agent account, who is redirected to their own portal."""
    return hasattr(user, "agent_profile") and not getattr(user, "is_staff", False)