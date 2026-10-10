"""
Sidebar counters.

The notification bell was the only place an agent-submitted prospect was
visible to staff. That is a poor discovery path and a poor queue: a new
referral produces one more bell entry, so a busy day buries it, and there is
no way to answer "how many are waiting?" without opening every notification.

This puts the count on the menu itself, where someone working the pipeline
will actually look.

`prospect_count` is the number of referrals still awaiting a staff decision
-- submitted, or under review. Converted and declined are finished and are
deliberately excluded, so the badge means "there is work here" rather than
"there has ever been work here".

Cached for a minute. It is read on every page render, and a COUNT on
`prospect` per request is not something to pay for a badge.
"""

from django.core.cache import cache

PROSPECT_COUNT_KEY = "sidebar_prospect_count"
PROSPECT_COUNT_TTL = 60


def _open_prospect_count():
    from billing.models import Prospect

    return Prospect.objects.filter(
        status__in=["submitted", "under_review"]
    ).count()


def sidebar_counts(request):
    """Adds `prospect_count` to every template context.

    Returns 0 for anyone without billing access so the badge never leaks the
    size of the pipeline to a Technician or an Agent, who have no business
    working it.
    """
    zero = {"prospect_count": 0}

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return zero

    perms = getattr(user, "role_perms", None)
    if perms is None or not getattr(perms, "can_access_billing", False):
        return zero
    # Agents have their own referrals view; they must not see staff's queue.
    if getattr(user, "agent_profile", None) and not user.is_staff:
        return zero

    count = cache.get(PROSPECT_COUNT_KEY)
    if count is None:
        try:
            count = _open_prospect_count()
        except Exception:
            # A badge is never worth a 500.
            return zero
        cache.set(PROSPECT_COUNT_KEY, count, PROSPECT_COUNT_TTL)
    return {"prospect_count": count}
