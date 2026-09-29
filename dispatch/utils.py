import logging
import re
import time
from django.utils import timezone
from django.db import transaction, IntegrityError

logger = logging.getLogger(__name__)


def log_audit(action, entity_type, entity_id, actor, summary=None, before=None, after=None):
    """Single source of truth for dispatch audit logging. Never raises."""
    from dispatch.models import AuditLog
    try:
        AuditLog.objects.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
            summary=summary,
            before_data=before,
            after_data=after,
        )
    except Exception as e:
        logger.warning(f"Failed to record dispatch audit log: {e}")


def generate_ticket_number(ticket_type="INSTALLATION", max_attempts=5):
    """
    Central ticket-number generator used by staff, customer portal, and dispatch tickets.
    Format: GT-YYYYMMDD-XXXX (e.g. GT-20260924-0001)
    Keeps legacy ticket numbers untouched.
    Safe under concurrency with bounded retry on collision.
    """
    from dispatch.models import JobTicket
    today_str = timezone.now().strftime("%Y%m%d")
    prefix = f"GT-{today_str}-"

    for attempt in range(max_attempts):
        try:
            with transaction.atomic():
                # Find the highest existing ticket number for today with select_for_update
                last_ticket = (
                    JobTicket.objects.select_for_update()
                    .filter(ticket_number__startswith=prefix)
                    .order_by("-ticket_number")
                    .first()
                )
                if last_ticket and last_ticket.ticket_number:
                    try:
                        # Extract sequence number from e.g. GT-20260924-0005
                        match = re.search(r"-(\d+)$", last_ticket.ticket_number)
                        if match:
                            next_seq = int(match.group(1)) + 1
                        else:
                            count = JobTicket.objects.filter(ticket_number__startswith=prefix).count()
                            next_seq = count + 1
                    except Exception:
                        count = JobTicket.objects.filter(ticket_number__startswith=prefix).count()
                        next_seq = count + 1
                else:
                    count = JobTicket.objects.filter(ticket_number__startswith=prefix).count()
                    next_seq = count + 1

                candidate = f"{prefix}{next_seq:04d}"
                while JobTicket.objects.filter(ticket_number=candidate).exists():
                    next_seq += 1
                    candidate = f"{prefix}{next_seq:04d}"

                return candidate
        except IntegrityError:
            if attempt == max_attempts - 1:
                raise
            time.sleep(0.05 * (attempt + 1))
