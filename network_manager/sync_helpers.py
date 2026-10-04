"""
Shared helpers for the Sync Manager.

THE BOUNCER MODEL
-----------------
The owner described the Sync Manager as a bouncer at a club door:

    the export is one source of truth, the routers are the other, and the
    SYSTEM sits in the middle until a human approves

Two rules follow from that, and this module exists to enforce them:

1. EXISTENCE IS NOT APPROVAL. An account can be present in both the database
   and the router and still be unverified. Only a human action moves it to
   "approved", and only that action may write to a router.

2. THE COMMENT IS THE RECEIPT. The system recognises its own secrets by the
   `Name | Barangay` comment on the router. A secret written without that
   separator becomes an unrecognisable orphan, which is precisely how "Missing
   /Invalid Comment" accounts appear. Every writer must use ONE function to
   build the comment, or bulk operations will silently produce garbage that
   the single-account path does not.

Rule 2 was violated: bulk push passed a bare name while single push passed
"Name | Barangay". Any account touched by bulk push was permanently flagged.
"""

from billing.models import Customer, SystemLog


def _clean(value, limit=None):
    """Flatten a value to a single printable line.

    MikroTik comments are single-line. A newline pasted in from an address
    field would truncate the comment at the first line break and silently
    drop the separator, producing an unparseable secret.
    """
    text = str(value or "")
    for ch in ("\r", "\n", "\t"):
        text = text.replace(ch, " ")
    text = " ".join(text.split())
    if limit and len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return text


def build_router_comment(customer):
    """Build the canonical router comment: 'Full Name | Barangay'.

    This is the ONLY place a comment may be constructed. If a second writer
    ever formats it differently, previously-written secrets stop matching and
    the Sync Manager fills with false "Missing/Invalid Comment" reports.

    Falls back to a trimmed address when the barangay is unknown, because an
    account with no barangay is still identifiable by where it lives.
    """
    name = _clean(customer.full_name or customer.pppoe_username)
    if customer.barangay and customer.barangay.name:
        return "{} | {}".format(name, _clean(customer.barangay.name))
    if customer.address:
        return "{} | {}".format(name, _clean(customer.address, limit=30))
    # No location at all. Still emit the separator so the secret is
    # parseable; an unparseable comment is worse than a sparse one.
    return "{} | (no barangay)".format(name)


def desired_profile(customer):
    """The profile name the router should carry for this customer.

    Uses `SubscriptionPlan.effective_router_profile` so a plan can have a
    customer-facing name ("GTipid Fiber 1000") that maps to a technical router
    profile ("pppoe-100m_1k"). Falls back to the plan name when no profile is
    set, which is the previous behaviour.
    """
    if not customer.plan:
        return "default"
    return customer.plan.effective_router_profile


def mark_synced(customer, device, actor):
    """Record a successful, human-approved router write.

    Sets sync_status to Synced and links the router, so the account stops
    appearing in the approval queue. Without this the system keeps claiming
    the account is Unverified even after a successful write, and staff cannot
    tell whether the sync happened.
    """
    changed = []
    if customer.sync_status != "Synced":
        changed.append(
            "sync_status: {} -> Synced".format(customer.sync_status or "(none)")
        )
        customer.sync_status = "Synced"
    if customer.mikrotik_device_id != device.id:
        changed.append(
            "mikrotik_device: {} -> {}".format(
                customer.mikrotik_device.device_name if customer.mikrotik_device
                else "none",
                device.device_name,
            )
        )
        customer.mikrotik_device = device

    if changed:
        # A queryset UPDATE, NOT customer.save().
        #
        # Customer.save() runs billing/signals.py, whose staging receiver
        # rewrites sync_status to "Pending" on every save that is not an
        # explicit push_to_router. That silently undid the approval: the
        # account went to the router, then straight back into the queue. An
        # approval is a recorded fact about the router, so it must not pass
        # through the staging path that exists to QUEUE work.
        Customer.objects.filter(pk=customer.pk).update(
            sync_status="Synced", mikrotik_device=device
        )
        customer.sync_status = "Synced"
        customer.mikrotik_device = device

    SystemLog.objects.create(
        table_name="Customer",
        record_id=str(customer.id),
        action="ROUTER_SYNC",
        changed_by=getattr(actor, "username", None) or "System",
        target_name=customer.full_name,
        old_data="",
        new_data=(
            "Approved and written to {} by Sync Manager. {}"
            .format(device.device_name, "; ".join(changed) or "no field change")
        ),
    )
    return changed


def router_write_blocked_message():
    """Human wording for a refused write, so the cause is never a mystery."""
    return (
        "Router write refused because ROUTER_MODE=read_only. The system can "
        "still READ the router and compare it, but it cannot change anything "
        "until router credentials are confirmed and an admin sets "
        "ROUTER_MODE=live. Nothing was changed."
    )


def account_needs_approval(customer):
    """Does this account still require a human decision?

    Unverified = never checked against a router. Blocked = a write was
    attempted and refused. No device = cannot be traced to a router at all.
    """
    return (
        customer.sync_status in ("Unverified", "Blocked")
        or not customer.mikrotik_device_id
    )


def approval_reasons(customer):
    """Why this account is sitting in the queue, in plain words."""
    reasons = []
    if not customer.mikrotik_device_id:
        reasons.append("Not assigned to a router")
    if customer.sync_status == "Unverified":
        reasons.append("Never verified against a router")
    elif customer.sync_status == "Blocked":
        reasons.append("A previous write was refused")
    elif customer.sync_status == "Failed":
        reasons.append("The last write failed")
    return reasons