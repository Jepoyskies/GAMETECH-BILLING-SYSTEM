from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from billing.decorators import role_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from network_manager.models import MikrotikDevice
from network_manager.services import MikrotikAPI
from network_manager.sync_helpers import (
    account_needs_approval,
    approval_reasons,
    build_router_comment,
    desired_profile,
    mark_pair_approvals,
    mark_synced,
    router_write_blocked_message,
)

# Deleting secrets from a live router is irreversible from this screen. Small
# batches keep a mistake recoverable.
BULK_DELETE_MAX = 25

def _plan_health():
    """Plan problems, never fatal to the page."""
    try:
        from billing.services.plan_health import plan_health
        return plan_health()
    except Exception as exc:
        return {"clean": True, "ambiguous": [], "unmapped": [], "error": str(exc),
                "total_plans": 0, "plans_with_profile": 0}


@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_manager(request, device_id):
    from billing.models import Customer
    from network_manager.sync_services import MikrotikAPI as MikrotikSyncAPI
    
    device = get_object_or_404(MikrotikDevice, id=device_id)
    
    # 1. Fetch Django Customers for this device OR unassigned customers
    from django.db.models import Q
    django_customers = Customer.objects.filter(
        Q(mikrotik_device=device) | Q(mikrotik_device__isnull=True)
    ).exclude(pppoe_username__isnull=True).exclude(pppoe_username='')
    django_usernames = set(django_customers.values_list('pppoe_username', flat=True))

    # Stamp the pairing audit trail onto every row BEFORE the categorise loop,
    # so account_needs_approval() and the Approve badge both answer the same
    # question: has a human actually paired this, or did it merely get pushed?
    # Iterating here also caches the queryset, so the map below reuses it.
    mark_pair_approvals(django_customers)
    
    # 2. Fetch Router Users using the Sync API
    #
    # Respect the circuit breaker BEFORE dialling. Opening this page on a
    # router we already know is dead used to block for ~15s on the socket
    # timeout, every single visit, which reads as "the site is broken". The
    # breaker already knows; say so immediately instead of waiting to find out.
    from django.core.cache import cache

    # ?force=1 lets an operator re-test a router they just fixed, instead of
    # waiting out the breaker's backoff.
    if request.GET.get("force") == "1":
        cache.delete(f"router_unreachable_{device.id}")
        cache.delete(f"router_unreachable_{device.id}_n")

    known_down = bool(cache.get(f"router_unreachable_{device.id}"))
    if known_down:
        result = {
            "success": False,
            "error": (
                f"{device.device_name} did not answer the last check, so its "
                f"secrets cannot be compared right now. This is a known, "
                f"cached outage - we are not retrying on every page load. "
                f"Check the cable, power and IP, then use Retry now."
            ),
        }
    else:
        api = MikrotikSyncAPI(
            ip_address=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=device.api_port
        )
        result = api.get_all_pppoe_users()

    clean_orphans = []
    suspicious_users = []
    missing_on_router = []
    synced = []
    needs_review = []

    if result.get('success'):
        router_users = result.get('data', [])
        router_usernames = set(u.get('name') for u in router_users if u.get('name'))

        # Categorize
        # Create a fast lookup dict for django customers by pppoe_username
        django_customer_map = {dc.pppoe_username: dc for dc in django_customers}

        for ru in router_users:
            name = ru.get('name')
            if not name:
                continue

            is_in_system = name in django_usernames
            if is_in_system:
                ru['customer'] = django_customer_map.get(name)
                ru['is_in_system'] = True
            else:
                ru['is_in_system'] = False

            if is_in_system:
                # Compare the system's intent against what the router actually
                # has, so the table shows the DIFF rather than just "both
                # exist". Staff need to see WHAT differs to trust the page.
                dc = django_customer_map.get(name)
                want_profile = dc.plan.effective_router_profile if dc and dc.plan else "default"
                have_profile = ru.get('profile')
                have_pw = ru.get('password')
                want_pw = dc.pppoe_password if dc else None
                drift_fields = []
                if want_profile and have_profile and want_profile != have_profile:
                    drift_fields.append('profile')
                if want_pw and have_pw and str(want_pw) != str(have_pw):
                    drift_fields.append('password')
                ru['drift'] = bool(drift_fields)
                ru['want_profile'] = want_profile
                ru['have_profile'] = have_profile
                ru['drift_fields'] = drift_fields

                # The router's own enabled/disabled flag is the ground truth
                # for "is this customer actually cut off?". Without it a
                # lapsed record and a live line look identical, which is
                # exactly the question a collections review has to answer.
                # MikroTik returns disabled as the STRING "true"/"false", so bool() is
                # useless here: bool("false") is True. Every secret therefore
                # read as CUT OFF, which pushed paying customers into the review
                # queue permanently and made "Paid, Cut Off" the default verdict
                # instead of a real exception. sync_services.py already
                # normalises this; do the same here.
                router_disabled = str(ru.get('disabled', '')).strip().lower() in (
                    "true", "yes", "1",
                )
                ru['router_disabled'] = router_disabled
                ru['router_enabled'] = not router_disabled

                # Cross-domain disagreement, in both directions:
                #   system says lapsed, router says still enabled
                #     -> "Connected but Unpaid": collect, do NOT suspend.
                #   system says fine, router says disabled
                #     -> a paying customer is cut off. Reconnect.
                system_thinks_off = bool(
                    dc and (
                        dc.status in ('suspended', 'expired', 'inactive', 'past_due')
                        or (dc.expires_at and dc.expires_at <= timezone.now())
                    )
                )
                ru['connected_but_unpaid'] = bool(system_thinks_off and not router_disabled)
                ru['should_be_disabled'] = system_thinks_off
                ru['state_mismatch'] = bool(
                    ru['connected_but_unpaid']
                    or (router_disabled and not system_thinks_off)
                )

                # --- THE BOUNCER CHECK -----------------------------------
                # Existing in both places is NOT the same as APPROVED.
                #
                # An account imported from the legacy system exists in the
                # database and (usually) on the router, but nobody has ever
                # confirmed the two actually belong together. Treating
                # "present in both" as "good" let unverified accounts appear
                # under Active Users the moment a router came online, which is
                # exactly the automatic approval this page exists to prevent.
                #
                # These must all reach a human before they count as connected:
                #   sync_status Unverified -> never checked against a router
                #   sync_status Blocked    -> a push was attempted and refused
                #   no mikrotik_device     -> cannot be traced to a router at all
                never_verified = account_needs_approval(dc)
                unlinked = not dc.mikrotik_device_id
                ru['never_verified'] = never_verified
                ru['unlinked'] = unlinked
                ru['awaiting_approval'] = bool(
                    never_verified or unlinked or ru['drift'] or ru['state_mismatch']
                )
                ru['approval_reasons'] = approval_reasons(dc)

                if ru['awaiting_approval'] or ru.get('is_suspicious'):
                    needs_review.append(ru)
                else:
                    synced.append(ru)
            elif ru.get('is_suspicious'):
                suspicious_users.append(ru)
            else:
                clean_orphans.append(ru)

        for dc in django_customers:
            if dc.pppoe_username not in router_usernames:
                missing_on_router.append(dc)
    # No flash message on failure: the template's offline card already shows
    # router_error. A flash duplicated it as a toast AND an inline alert.

    from billing.models import Barangay
    
    all_routers = MikrotikDevice.objects.all()
    barangays = Barangay.objects.all().order_by('name')

    context = {
        'device': device,
        'clean_orphans': clean_orphans,
        'suspicious_users': suspicious_users,
        'missing_on_router': missing_on_router,
        'synced': synced,
        'needs_review': needs_review,
        'all_routers': all_routers,
        'barangays': barangays,
        'api_success': result.get('success', False),
        'router_error': '' if result.get('success') else result.get('error', ''),
        'known_down': known_down,
        'router_mode': getattr(__import__('django.conf', fromlist=['settings']).settings, 'ROUTER_MODE', 'read_only'),
        'count_synced': len(synced),
        'count_needs_review': len(needs_review),
        'count_missing': len(missing_on_router),
        'count_orphans': len(clean_orphans),
        'count_suspicious': len(suspicious_users),
        # Plan-level problems that would otherwise show up as unexplained
        # drift: duplicate-priced plans at different speeds, and plans with no
        # MikroTik profile mapped. Surfaced here so staff see WHY a row drifts
        # before blaming the router.
        'plan_health': _plan_health(),
    }
    
    return render(request, 'network_manager/sync_manager.html', context)

def push_blockers(customer):
    """Reasons this account must not be given a router secret without a human.

    Delegates to Customer.push_blocked_reasons so the gate, the bulk gate and
    the badge the operator reads can never disagree. Kept as a named function
    because "why is this push refused" is a question the view asks in four
    places and the answer must be identical in all of them.

    Deliberately undecorated: this is a pure helper, not a view. It was briefly
    carrying sync_push_user's @role_required/@login_required, which both broke
    callers and left sync_push_user itself unauthenticated.
    """
    return customer.push_blocked_reasons


def _push_one(api, customer, device, actor):
    """Write a single secret to the router and record the approval.

    Shared by the single-push, bulk-push and admin-override paths so all three
    produce byte-identical secrets. Divergence here is what created the
    "Missing/Invalid Comment" noise: two writers, two comment formats.
    """
    res = api.add_pppoe_user(
        name=customer.pppoe_username,
        password=customer.pppoe_password,
        profile=desired_profile(customer),
        comment=build_router_comment(customer),
    )
    if res.get('success'):
        mark_synced(customer, device, actor)
    elif 'read_only' in str(res.get('error', '')).lower():
        customer.sync_status = "Blocked"
        customer.save(update_fields=["sync_status"])
    else:
        customer.sync_status = "Failed"
        customer.save(update_fields=["sync_status"])
    return res


def _approve_customers(customers, device, actor):
    """Record a human's approval of accounts that already match the router.

    WHY THIS EXISTS
    ---------------
    A PPPoE secret already sitting on the router proves the old system created
    it. It does not prove anyone has looked at it. During a cutover the old
    billing system is often still writing to the same routers, so "it happens
    to be there" is exactly the kind of assumption that should not be enough to
    call an account live.

    So approval is explicit and separate from provisioning:
      * the router is READ to confirm the secret exists
      * the router is NEVER written -- nothing here can change a subscriber
      * the operator's name is logged, and sync_status moves Unverified -> Synced

    Returns (approved, skipped_blocked, not_on_router).
    """
    from network_manager.sync_services import MikrotikAPI as MikrotikSyncAPI

    api = MikrotikSyncAPI(
        ip_address=device.ip_address,
        username=device.api_username,
        password=device.api_password,
        port=device.api_port
    )
    result = api.get_all_pppoe_users()
    if not result.get('success'):
        raise RuntimeError(
            "Could not read {}: {}".format(device.device_name, result.get('error'))
        )
    on_router = {u.get('name'): u for u in (result.get('data') or []) if u.get('name')}

    # Imported here, not at module scope: this module is imported very early by
    # the URL conf and a top-level billing.models import risks a circular
    # import. Both names below must be in this function's namespace -- a
    # missing one raised NameError *inside* the atomic block, which rolled the
    # approval back while the operator saw only a generic failure.
    from billing.models import Customer, SystemLog

    approved = blocked = absent = 0
    for customer in customers:
        # Unpaid / no-expiry is refused here exactly as it is on Push.
        # Approving asserts this account SHOULD be live, so it must not become
        # the easy way round the payment gate.
        if push_blockers(customer):
            blocked += 1
            continue

        secret = on_router.get(customer.pppoe_username)
        if secret is None:
            absent += 1
            continue

        # Status and audit trail must land together. Writing the status first
        # meant a failure in the log step left an approval recorded with no
        # evidence of who made it -- the one thing this whole gate exists to
        # guarantee. atomic() keeps them inseparable.
        with transaction.atomic():
            was = customer.sync_status
            Customer.objects.filter(pk=customer.pk).update(sync_status="Synced")

            SystemLog.objects.create(
                table_name="Customer",
                record_id=str(customer.id),
                action="SYNC_PAIR_APPROVED",
                changed_by=actor.username,
                target_name=customer.full_name,
                old_data="sync_status={}".format(was),
                new_data=(
                    "Approved by {}. PPPoE '{}' verified present on {} "
                    "(enabled={}, profile='{}'). Router not modified."
                ).format(
                    actor.username, customer.pppoe_username, device.device_name,
                    secret.get('is_enabled'), secret.get('profile'),
                ),
            )
        customer.sync_status = "Synced"
        approved += 1

    return approved, blocked, absent


@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_approve_match(request, device_id):
    """Approve one already-matched account. Reads the router, never writes it."""
    if request.method != 'POST':
        return redirect('sync_manager_device', device_id=device_id)

    device = get_object_or_404(MikrotikDevice, id=device_id)
    username = request.POST.get('pppoe_username')

    from billing.models import Customer
    customer = Customer.objects.filter(
        pppoe_username=username, mikrotik_device=device
    ).first()
    if not customer:
        messages.error(request, "No customer matches that PPPoE username on this router.")
        return redirect('sync_manager_device', device_id=device_id)

    try:
        approved, blocked, absent = _approve_customers([customer], device, request.user)
    except Exception as e:
        messages.error(request, "Approval failed: {}".format(e))
        return redirect('sync_manager_device', device_id=device_id)

    if approved:
        messages.success(
            request, "Approved {} on {}. Recorded in System Logs.".format(
                customer.full_name, device.device_name)
        )
    elif blocked:
        reasons = "; ".join(push_blockers(customer))
        messages.error(
            request,
            "Refused: {} is {} — admin override required before this account can "
            "be treated as live.".format(customer.full_name, reasons)
        )
    else:
        messages.error(
            request,
            "{} is not actually on {}. Use Push instead.".format(
                customer.pppoe_username, device.device_name)
        )
    return redirect('sync_manager_device', device_id=device_id)


@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_override_push(request, device_id):
    """Admin-authorised push for an account blocked by push_blockers().

    The CSR who pressed Push is exactly the person being blocked, so this
    requires a SEPARATE Admin's credentials. There is no fallback to
    request.user: accepting the operator's own password would make the gate
    decoration. Every approval is written to SystemLog with both names.
    """
    if request.method != 'POST':
        return redirect('sync_manager_device', device_id=device_id)

    device = get_object_or_404(MikrotikDevice, id=device_id)
    pppoe_username = request.POST.get('pppoe_username')

    from billing.models import Customer, SystemLog
    from network_manager.sync_services import MikrotikAPI as MikrotikSyncAPI
    from django.contrib.auth import get_user_model
    from django.contrib.auth.hashers import check_password

    customer = Customer.objects.filter(
        pppoe_username=pppoe_username, mikrotik_device=device
    ).first()
    if not customer:
        messages.error(request, "Customer not found on this router.")
        return redirect('sync_manager_device', device_id=device_id)

    admin_username = (request.POST.get('admin_username') or '').strip()
    admin_password = request.POST.get('admin_password') or ''

    admin_user = None
    if admin_username:
        admin_user = get_user_model().objects.filter(
            username__iexact=admin_username, is_active=True
        ).first()

    if admin_user is None or not check_password(admin_password, admin_user.password):
        messages.error(
            request,
            "Override denied: '{}' is not a valid Admin account, or the password "
            "is incorrect.".format(admin_username or "(blank)"),
        )
        return redirect('sync_manager_device', device_id=device_id)

    if not (admin_user.is_superuser or getattr(admin_user, "role", "") == "Admin"):
        messages.error(
            request,
            "Override denied: {} is not an Admin.".format(admin_user.username),
        )
        return redirect('sync_manager_device', device_id=device_id)

    reasons = push_blockers(customer)
    if not reasons:
        messages.info(
            request,
            "{} has no blocking conditions — use the normal Push button."
            .format(customer.full_name),
        )
        return redirect('sync_manager_device', device_id=device_id)

    api = MikrotikSyncAPI(
        ip_address=device.ip_address,
        username=device.api_username,
        password=device.api_password,
        port=device.api_port
    )
    res = _push_one(api, customer, device, request.user)

    if res.get('success'):
        SystemLog.objects.create(
            table_name="Customer",
            record_id=str(customer.id),
            action="SYNC_ADMIN_OVERRIDE",
            changed_by=request.user.username,
            target_name=customer.full_name,
            old_data=(
                "status={}, expires_at={}".format(
                    customer.status, customer.expires_at or "NONE"
                )
            ),
            new_data=(
                "Blocked by: {}. Pressed by {}. Approved by Admin {}. "
                "Pushed PPPoE '{}' to {} with profile '{}'."
            ).format(
                "; ".join(reasons),
                request.user.username,
                admin_user.username,
                customer.pppoe_username,
                device.device_name,
                desired_profile(customer),
            ),
        )
        messages.success(
            request,
            "Override approved by {}. {} is now live on {}."
            .format(admin_user.username, customer.full_name, device.device_name),
        )
    else:
        messages.error(
            request,
            "Override approved by {} but the router refused: {}".format(
                admin_user.username, res.get('error')
            ),
        )

    return redirect('sync_manager_device', device_id=device_id)


@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_push_user(request, device_id):
    if request.method == 'POST':
        pppoe_username = request.POST.get('pppoe_username')
        device = get_object_or_404(MikrotikDevice, id=device_id)
        
        from billing.models import Customer
        from network_manager.sync_services import MikrotikAPI as MikrotikSyncAPI
        
        customer = get_object_or_404(Customer, pppoe_username=pppoe_username, mikrotik_device=device)

        # Gate lives here, not in the template, so the bulk path and any
        # hand-posted form hit the same rule.
        blockers = push_blockers(customer)
        if blockers:
            messages.error(
                request,
                "Blocked — {} not pushed: {}. An Admin must authorise this."
                .format(customer.pppoe_username, "; ".join(blockers)),
            )
            return redirect('sync_manager_device', device_id=device_id)

        api = MikrotikSyncAPI(
            ip_address=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=device.api_port
        )

        # Canonical comment + profile. Single source of truth so a bulk push
        # can never write a different format from a single push.
        profile = desired_profile(customer)
        comment = build_router_comment(customer)

        result = api.add_pppoe_user(
            name=customer.pppoe_username,
            password=customer.pppoe_password,
            profile=profile,
            comment=comment
        )

        if result.get('success'):
            mark_synced(customer, device, request.user)
            messages.success(request, result.get('message'))
        elif 'read_only' in str(result.get('error', '')).lower():
            # Do not let a refused write look like a success.
            customer.sync_status = "Blocked"
            customer.save(update_fields=["sync_status"])
            messages.warning(request, router_write_blocked_message())
        else:
            customer.sync_status = "Failed"
            customer.save(update_fields=["sync_status"])
            messages.error(request, f"Failed to push user: {result.get('error')}")

    return redirect('sync_manager_device', device_id=device_id)

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_autofix_user(request, device_id):
    """Auto-fixes a synced customer's router profile and comment to match the system database."""
    if request.method == 'POST':
        pppoe_username = request.POST.get('pppoe_username')
        device = get_object_or_404(MikrotikDevice, id=device_id)
        
        from billing.models import Customer
        from network_manager.sync_services import MikrotikAPI as MikrotikSyncAPI
        
        customer = get_object_or_404(Customer, pppoe_username=pppoe_username)
        
        api = MikrotikSyncAPI(
            ip_address=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=device.api_port
        )
        
        profile = desired_profile(customer)
        comment = build_router_comment(customer)

        result = api.add_pppoe_user(
            name=customer.pppoe_username,
            password=customer.pppoe_password,
            profile=profile,
            comment=comment
        )

        if result.get('success'):
            # ALSO assign the router. Without this an account with no
            # mikrotik_device stays unlinked after a successful fix, so it
            # remains invisible on the customers page and keeps appearing in
            # this queue forever.
            mark_synced(customer, device, request.user)
            messages.success(
                request,
                f"Auto-Fixed '{pppoe_username}' and linked it to {device.device_name}.",
            )
        elif 'read_only' in str(result.get('error', '')).lower():
            customer.sync_status = "Blocked"
            customer.save(update_fields=["sync_status"])
            messages.warning(request, router_write_blocked_message())
        else:
            customer.sync_status = "Failed"
            customer.save(update_fields=["sync_status"])
            messages.error(
                request,
                f"Failed to Auto-Fix '{pppoe_username}': {result.get('error')}",
            )
            
    return redirect('sync_manager_device', device_id=device_id)

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_delete_user(request, device_id):
    if request.method == 'POST':
        pppoe_username = request.POST.get('pppoe_username')
        device = get_object_or_404(MikrotikDevice, id=device_id)
        
        from network_manager.sync_services import MikrotikAPI as MikrotikSyncAPI
        
        api = MikrotikSyncAPI(
            ip_address=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=device.api_port
        )
        
        result = api.delete_pppoe_user(name=pppoe_username)
        
        if result.get('success'):
            messages.success(request, result.get('message'))
        else:
            messages.error(request, f"Failed to delete user: {result.get('error')}")
            
    return redirect('sync_manager_device', device_id=device_id)

@role_required(['Admin', 'Editor', 'CSR'])
@login_required
def sync_bulk_action(request, device_id):
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        usernames = request.POST.getlist('selected_users')
        device = get_object_or_404(MikrotikDevice, id=device_id)
        
        if not usernames:
            messages.warning(request, "No users selected for bulk action.")
            return redirect('sync_manager_device', device_id=device_id)

        from billing.models import Customer
        from network_manager.sync_services import MikrotikAPI as MikrotikSyncAPI
        
        api = MikrotikSyncAPI(
            ip_address=device.ip_address,
            username=device.api_username,
            password=device.api_password,
            port=device.api_port
        )

        success_count = 0
        error_count = 0

        if action == 'bulk_delete':
            # Deleting a secret from a live router cuts a customer's internet.
            # Refuse anything the system recognises as a real subscriber
            # unless the operator states the intent explicitly, and never
            # bulk-delete more than a handful without a second signal.
            known = [
                u for u in usernames
                if Customer.objects.filter(pppoe_username=u).exists()
            ]
            if known and request.POST.get('confirm_delete_subscribers') != 'yes':
                messages.error(
                    request,
                    "Refused: {} of those accounts exist in the system as real "
                    "subscribers. Deleting them cuts their internet. Tick the "
                    "confirmation box to proceed.".format(len(known)),
                )
                return redirect('sync_manager_device', device_id=device_id)
            if len(usernames) > BULK_DELETE_MAX:
                messages.error(
                    request,
                    "Refused: {} accounts is too many to delete at once. The "
                    "limit is {}. Delete in reviewed batches so a mistake is "
                    "recoverable.".format(len(usernames), BULK_DELETE_MAX),
                )
                return redirect('sync_manager_device', device_id=device_id)

            blocked_writes = 0
            for uname in usernames:
                res = api.delete_pppoe_user(name=uname)
                if res.get('success'):
                    success_count += 1
                else:
                    error_count += 1
                    if 'read_only' in str(res.get('error', '')).lower():
                        blocked_writes += 1
            if blocked_writes:
                messages.warning(
                    request,
                    "Bulk Delete: {} deleted, {} failed. {} were refused by "
                    "ROUTER_MODE=read_only -- nothing was removed."
                    .format(success_count, error_count, blocked_writes),
                )
            else:
                messages.success(
                    request, f"Bulk Delete: {success_count} deleted, {error_count} failed.")

        elif action == 'bulk_approve':
            # Human sign-off for accounts that already match the router. Reads
            # only: nothing here writes to hardware, so approving can never be
            # the thing that changes a subscriber's service.
            from billing.models import Customer as _C
            ids = request.POST.getlist('customer_ids')
            names = request.POST.getlist('selected_users')
            targets = _C.objects.filter(mikrotik_device=device)
            if ids:
                targets = targets.filter(id__in=ids)
            elif names:
                targets = targets.filter(pppoe_username__in=names)
            else:
                messages.warning(
                    request,
                    "Nothing selected to approve. Tick the accounts you have "
                    "reviewed, then press Approve.",
                )
                return redirect('sync_manager_device', device_id=device_id)

            targets = list(targets.select_related("plan"))
            try:
                approved, blocked, absent = _approve_customers(
                    targets, device, request.user
                )
            except Exception as e:
                messages.error(request, "Approval failed: {}".format(e))
                return redirect('sync_manager_device', device_id=device_id)

            parts = ["{} approved".format(approved)]
            if blocked:
                parts.append("{} held back for unpaid/no-expiry".format(blocked))
            if absent:
                parts.append("{} were not actually on the router".format(absent))
            messages.success(
                request,
                "Pairing approved on {}: {}. Router not modified.".format(
                    device.device_name, ", ".join(parts))
            )

        elif action == 'bulk_push':
            # Same canonical comment as the single-account path. Passing a bare
            # name here produced secrets the system could not recognise, which
            # is what "Missing/Invalid Comment" actually was.
            blocked_writes = 0
            gated = []
            for uname in usernames:
                customer = Customer.objects.filter(pppoe_username=uname).first()
                if not customer:
                    error_count += 1
                    continue
                # Same gate as the single-account path. Bulk must not become
                # the way around it: selecting 200 rows is exactly how an
                # unpaid, un-expiring account would silently go live.
                blockers = push_blockers(customer)
                if blockers:
                    gated.append("{} ({})".format(uname, "; ".join(blockers)))
                    error_count += 1
                    continue
                res = _push_one(api, customer, device, request.user)
                if res.get('success'):
                    success_count += 1
                else:
                    error_count += 1
                    if 'read_only' in str(res.get('error', '')).lower():
                        blocked_writes += 1

            if gated:
                messages.warning(
                    request,
                    "Bulk Push: {} approved, {} not pushed. {} account(s) were "
                    "held back for unpaid/no-expiry and need an Admin override: {}"
                    .format(
                        success_count, error_count, len(gated),
                        ", ".join(gated[:8]) + (" ..." if len(gated) > 8 else ""),
                    ),
                )
            elif blocked_writes:
                messages.warning(
                    request,
                    "Bulk Push: {} approved, {} failed. {} were refused by "
                    "ROUTER_MODE=read_only and are now marked Blocked -- they "
                    "stay in the queue for when writes are enabled."
                    .format(success_count, error_count, blocked_writes),
                )
            else:
                messages.success(
                    request,
                    f"Bulk Push: {success_count} approved and written, "
                    f"{error_count} failed.")

        elif action == 'bulk_import':
            if not (request.user.is_superuser or request.user.has_perm("billing.import_router_subscribers")):
                messages.error(request, "Permission denied: Requires 'billing.import_router_subscribers' permission.")
                return redirect('sync_manager_device', device_id=device_id)

            # Let's fetch secrets to get passwords:
            all_users_res = api.get_all_pppoe_users()
            router_users_dict = {u['name']: u for u in all_users_res.get('data', [])} if all_users_res.get('success') else {}
            
            for uname in usernames:
                ru = router_users_dict.get(uname, {})
                if not Customer.objects.filter(pppoe_username=uname).exists():
                    new_cust = Customer.objects.create(
                        full_name=ru.get('comment') or uname,
                        pppoe_username=uname,
                        pppoe_password=ru.get('password', ''),
                        mikrotik_device=device,
                        status='inactive',
                        installation_status='installed',
                        installed_at=timezone.now(),
                        source='router_sync',
                        created_form_by='Bulk Import'
                    )
                    
                    from billing.models import SystemLog
                    SystemLog.objects.create(
                        table_name="Customer",
                        record_id=str(new_cust.id),
                        action="ADD",
                        changed_by=request.user.username if request.user.is_authenticated else "System",
                        target_name=new_cust.full_name,
                        old_data="",
                        new_data=f"Imported from {device.device_name} (Bulk Import)\nUsername: {uname}\nStatus: inactive"
                    )
                    
                    success_count += 1
                else:
                    error_count += 1

            from billing.models import SystemLog
            SystemLog.objects.create(
                table_name="Customer",
                record_id="0",
                action="ROUTER_SYNC_IMPORT",
                changed_by=request.user.username if request.user.is_authenticated else "System",
                target_name=device.device_name,
                old_data="",
                new_data=f"Bulk router import for {device.device_name}: {success_count} imported, {error_count} skipped (duplicates/errors)."
            )

            messages.success(request, f"Bulk Import: {success_count} imported, {error_count} skipped/failed.")

        else:
            messages.error(request, "Invalid bulk action.")

    return redirect('sync_manager_device', device_id=device_id)

