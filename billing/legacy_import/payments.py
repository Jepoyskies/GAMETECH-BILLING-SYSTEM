"""
Legacy payment import -- the missing ledger.

THE GAP THIS FILLS
------------------
The legacy export contains 12,571 payment rows across 1,959 subscribers.
`import_legacy_customers` imported CUSTOMERS but had no payment handling at
all, so the new system started with a completely empty ledger:

    production before this:  1 Payment row (the seed record)

That is not a cosmetic shortfall. Three things in the product read the ledger:

  * outstanding_balance / advance payment -- auto-suspend renews subscribers
    whose advance credit covers a month. With no history, nobody has credit,
    so auto-suspend would suspend paying customers.
  * first_payment_date -- the 60-day agent lock and the billing clock.
  * revenue reports, and the "Paid, Status Unknown" collections queue.

So the system's financial picture was simply wrong. This module restores it.

DESIGN CONSTRAINTS
------------------
1. IDEMPOTENT. Re-running must not duplicate money. Keyed on the legacy
   payment id, which is a stable primary key in the old system.
2. NEVER INVENTS MONEY. A payment whose username matches no customer is
   still imported (the money was real), but with customer=NULL and reported,
   never silently dropped.
3. READ-ONLY WITH RESPECTS TO CUSTOMERS. This writes Payment rows only. It
   must not touch status, expiry or balances -- recalculating those is a
   separate, deliberate decision for the owner (WORKING_RULES.md Rule 0).
4. SAFE TO RE-RUN. Safe on a partial file, safe on the full one.

The customer table is imported FIRST, so the username -> customer map is
already warm by the time payments arrive.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from billing.models import Customer, Payment, SystemLog

# Legacy rows whose username is not a real subscriber are kept, not deleted:
# the cash was collected by someone. They are reported so the owner can
# decide, rather than silently vanishing from the ledger.
ORPHAN_REASON = "legacy payment with no matching customer"


def _parse_dt(value):
    """Parse a legacy datetime string, or return None.

    The legacy system is full of '0000-00-00 00:00:00' and the literal string
    'NULL'. Both mean "no date", and both must not become year-1 timestamps.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text or text.upper() == "NULL" or text.startswith("0000-00-00"):
        return None
    try:
        dt = parse_datetime(text)
    except (ValueError, TypeError):
        return None
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def _parse_amount(value):
    """Legacy amounts are decimal strings; anything unparseable is 0.00."""
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _parse_days(value):
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def import_legacy_payments(rows, actor="legacy-import", dry_run=False):
    """Import legacy `payments` rows into the Payment ledger.

    `rows` is a list of (table_name, row_dict) pairs, or just row dicts from
    the payments table. Returns a summary dict.

    Idempotent via legacy_id: a row already imported is updated in place, not
    duplicated, so re-running the whole export is safe.
    """
    payment_rows = [
        r for r in rows if not isinstance(r, tuple) or r[0] == "payments"
    ]
    # Accept both shapes: (table, row) pairs from iter_rows, or bare dicts.
    payment_rows = [
        (r[1] if isinstance(r, tuple) else r) for r in payment_rows
    ]

    summary = {
        "seen": len(payment_rows),
        "created": 0,
        "updated": 0,
        "skipped_no_amount": 0,
        "orphans": [],
        "orphan_count": 0,
        "total_amount": Decimal("0.00"),
        "matched_customers": 0,
        "no_payment_history_customers": 0,
    }

    if not payment_rows:
        return summary

    usernames = {
        str(r.get("username") or "").strip()
        for r in payment_rows
        if str(r.get("username") or "").strip()
    }

    # One query for the whole map, rather than 12,000 lookups.
    customer_map = {}
    chunk = list(usernames)
    for i in range(0, len(chunk), 500):
        for c in Customer.objects.filter(pppoe_username__in=chunk[i:i + 500]):
            customer_map[c.pppoe_username] = c

    if dry_run:
        # A dry run happens BEFORE the customers are written, so the database
        # legitimately holds none of them. Matching only against the live DB
        # therefore reported EVERY payment username as an orphan (436 of 436 in
        # the rehearsal) when the true figure was 3. Match against the customers
        # in THIS dump as well, which is what the real run will match against.
        dump_usernames = set()
        for r in rows:
            table = r[0] if isinstance(r, tuple) else None
            row = r[1] if isinstance(r, tuple) else r
            if table == "customers" or (table is None and row.get("expires_at")):
                u = str(row.get("username") or "").strip()
                if u:
                    dump_usernames.add(u)

        known = set(customer_map) | dump_usernames
        summary["matched_customers"] = len(known & usernames)
        summary["orphan_count"] = len(usernames - known)
        summary["orphans"] = sorted(usernames - known)[:50]
        for r in payment_rows:
            amt = _parse_amount(r.get("amount"))
            if amt <= 0:
                summary["skipped_no_amount"] += 1
            else:
                summary["total_amount"] += amt
        return summary

    existing = {}
    for p in Payment.objects.filter(
        legacy_id__isnull=False, legacy_id__in=[
            str(r.get("id")).strip() for r in payment_rows if r.get("id")
        ]
    ):
        existing[p.legacy_id] = p

    to_create = []
    orphans_seen = set()

    for r in payment_rows:
        username = str(r.get("username") or "").strip()
        amount = _parse_amount(r.get("amount"))
        if amount <= 0:
            # A zero/negative payment is not revenue. Record nothing rather
            # than a meaningless row that would pollute the reports.
            summary["skipped_no_amount"] += 1
            continue

        customer = customer_map.get(username)
        if customer is None:
            if username not in orphans_seen:
                orphans_seen.add(username)
                summary["orphans"].append(username)
        else:
            summary["matched_customers"] += 1

        legacy_id = str(r.get("id") or "").strip() or None
        fields = {
            "customer": customer,
            "username": username or None,
            "plan_name": (r.get("plan_name") or None),
            "mikrotik_device_name": (r.get("mikrotik_devices") or None),
            "amount": amount,
            "days_paid": _parse_days(r.get("days")),
            "payment_method": (r.get("payment_method") or "legacy"),
            "reference_no": (r.get("reference_no") or None),
            "reason": (
                ORPHAN_REASON if customer is None
                else (r.get("reason") or None)
            ),
            "expires_at": _parse_dt(r.get("expires_at")),
            "payment_date_received": _parse_dt(r.get("payment_date_received")),
            "paid_at": _parse_dt(r.get("paid_at")),
            "adjusted_by": (r.get("adjusted_by") or None),
            "is_test_data": False,
        }

        current = existing.get(legacy_id) if legacy_id else None
        if current is None and legacy_id:
            # Might exist under a row we did not preload (e.g. partial re-run).
            current = Payment.objects.filter(legacy_id=legacy_id).first()

        if current is None:
            fields["legacy_id"] = legacy_id
            to_create.append(Payment(**fields))
            summary["created"] += 1
        else:
            for key, value in fields.items():
                setattr(current, key, value)
            summary["updated"] += 1
            _queued_updates.append(current)

        summary["total_amount"] += amount

    if to_create:
        Payment.objects.bulk_create(to_create, batch_size=500)

    if _queued_updates:
        Payment.objects.bulk_update(
            _queued_updates,
            [
                "customer", "username", "plan_name", "mikrotik_device_name",
                "amount", "days_paid", "payment_method", "reference_no",
                "reason", "expires_at", "payment_date_received", "paid_at",
                "adjusted_by",
            ],
            batch_size=500,
        )
        _queued_updates.clear()

    summary["orphan_count"] = len(summary["orphans"])

    if summary["created"] or summary["updated"]:
        SystemLog.objects.create(
            table_name="Payment",
            record_id="0",
            action="LEGACY_IMPORT",
            changed_by=getattr(actor, "username", None) or "legacy-import",
            target_name="Legacy payment ledger",
            old_data="",
            new_data=(
                "Imported {} payments ({} new, {} updated), total PHP {:,.2f}. "
                "{} payments had no matching customer and were kept with a "
                "reason so the cash stays visible."
                .format(
                    summary["created"] + summary["updated"],
                    summary["created"], summary["updated"],
                    summary["total_amount"], summary["orphan_count"],
                )
            ),
        )

    return summary


# Module-level scratch list, flushed inside import_legacy_payments. Kept out
# of the function signature so the public API stays one-argument simple.
_queued_updates = []