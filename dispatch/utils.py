import re
from django.utils import timezone
from django.db import transaction


def generate_ticket_number(ticket_type="INSTALLATION"):
    """
    Central ticket-number generator used by staff, customer portal, and dispatch tickets.
    Format: GT-YYYYMMDD-XXXX (e.g. GT-20260924-0001)
    Keeps legacy ticket numbers untouched.
    """
    from dispatch.models import JobTicket
    today_str = timezone.now().strftime("%Y%m%d")
    prefix = f"GT-{today_str}-"

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
            next_seq = 1

        candidate = f"{prefix}{next_seq:04d}"
        while JobTicket.objects.filter(ticket_number=candidate).exists():
            next_seq += 1
            candidate = f"{prefix}{next_seq:04d}"

        return candidate
