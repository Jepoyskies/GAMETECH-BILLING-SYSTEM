"""
Seed the mandatory technician-replacement reasons and backfill the ordered
handover history for tickets that predate this table.

Two jobs, both additive:

1. Replacement reasons are a ConfigOption list (module=DISPATCH,
   list_type=REPLACEMENT_REASON) so dispatch can add or retire a reason from
   the Management screen without a code change. Sir's example
   ("first tech only knew how to do the first part") is reason #1, not free text.

2. Existing JobTicket.technicians rows have no order and no history. We cannot
   recover who was first for tickets already worked, so every pre-existing
   technician on a ticket is backfilled at sequence 1 with is_current=True.
   That records "these techs were on it" truthfully without inventing an order
   we have no evidence for. Real ordering starts accruing from today forward.
"""
from django.db import migrations

# (label, sort_order). 'other' must stay last: selecting it forces the
# technician to type a note, which is what makes the reason meaningful.
REPLACEMENT_REASONS = [
    ("Skill mismatch (first tech could not finish the job)", 1),
    ("Technician unavailable / off duty", 2),
    ("Workload rebalancing across the team", 3),
    ("Job requires a different specialty or equipment", 4),
    ("Original job was cancelled or rescheduled", 5),
    ("Other (note required)", 6),
]


def seed_reasons(apps, schema_editor):
    ConfigOption = apps.get_model("dispatch", "ConfigOption")
    for label, order in REPLACEMENT_REASONS:
        ConfigOption.objects.get_or_create(
            list_type="REPLACEMENT_REASON",
            module="DISPATCH",
            label=label,
            defaults={"sort_order": order, "active": True, "hardcoded": True},
        )


def backfill_assignments(apps, schema_editor):
    JobTicket = apps.get_model("dispatch", "JobTicket")
    TicketTechnicianAssignment = apps.get_model("dispatch", "TicketTechnicianAssignment")
    for ticket in JobTicket.objects.all().prefetch_related("technicians"):
        for tech in ticket.technicians.all():
            TicketTechnicianAssignment.objects.get_or_create(
                job_ticket_id=ticket.id,
                technician_id=tech.id,
                sequence=1,
                defaults={"is_current": True},
            )


def unseed_reasons(apps, schema_editor):
    ConfigOption = apps.get_model("dispatch", "ConfigOption")
    ConfigOption.objects.filter(list_type="REPLACEMENT_REASON", module="DISPATCH").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("dispatch", "0017_jobticket_ont_modem_mac_alter_configoption_list_type_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_reasons, unseed_reasons),
        migrations.RunPython(backfill_assignments, migrations.RunPython.noop),
    ]