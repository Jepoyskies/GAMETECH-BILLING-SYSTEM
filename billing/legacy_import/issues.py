"""Customer records that need a human decision after a legacy import.

Nothing here deletes or silently repairs anything. The old PHP system is the
source of truth, so a record that looks wrong may be exactly right and only
Sir Rom can say. These buckets exist so every questionable customer is visible
in one place instead of hiding inside a list of 2,000.

Deliberately excludes `installation_status="pending"`: a pending install having
no expiry date is correct, not a problem.
"""

from datetime import timedelta

from django.utils import timezone

from billing.models import Customer

# Anything dated further out than this is almost certainly junk written by the
# old system rather than a real subscription. 2030/2031 dates were seen in the
# legacy export.
FUTURE_DATE_THRESHOLD_DAYS = 730


def _installed():
    return Customer.objects.filter(installation_status="installed").exclude(
        status__in=["pending", "closed_not_installed"]
    )


def get_issue_buckets():
    """Return {key: (label, queryset, why_it_matters)} for every problem bucket."""
    now = timezone.now()
    horizon = now + timedelta(days=FUTURE_DATE_THRESHOLD_DAYS)

    buckets = [
        (
            "no_expiry",
            "No expiration date",
            _installed().filter(expires_at__isnull=True),
            "Cannot be auto-suspended or auto-renewed. Keep active, set a date, or archive.",
        ),
        (
            "future_dated",
            "Suspicious future date",
            _installed().filter(expires_at__gt=horizon),
            "Expiry is years away. Usually junk written by the old system.",
        ),
        (
            "lapsed",
            "Lapsed",
            _installed().filter(expires_at__lt=now).exclude(expires_at__isnull=True),
            "Past due. Normal churn, but worth a look before going live.",
        ),
        (
            "no_plan",
            "No plan assigned",
            Customer.objects.filter(plan__isnull=True),
            "No price attached, so billing cannot compute what to charge.",
        ),
        (
            "no_router",
            "Not linked to a router",
            Customer.objects.filter(mikrotik_device__isnull=True),
            "Cannot be synced to or verified against any MikroTik.",
        ),
        (
            "no_password",
            "No PPPoE password",
            Customer.objects.filter(pppoe_password__isnull=True) | Customer.objects.filter(pppoe_password=""),
            "Cannot authenticate on the router.",
        ),
    ]

    out = {}
    for key, label, qs, why in buckets:
        qs = qs.distinct()
        out[key] = {
            "label": label,
            "why": why,
            "count": qs.count(),
            "queryset": qs.order_by("full_name")[:200],
            "truncated": max(qs.count() - 200, 0),
        }
    return out


def issue_summary():
    """Counts only -- for the KPI strip."""
    return {k: v["count"] for k, v in get_issue_buckets().items()}
