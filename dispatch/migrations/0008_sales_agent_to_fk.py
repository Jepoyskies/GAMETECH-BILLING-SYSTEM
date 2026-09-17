# Generated data migration to convert sales_agent CharField to ForeignKey(Agent) and add is_test_data

from django.db import migrations, models
import django.db.models.deletion


def migrate_sales_agents_forward(apps, schema_editor):
    Agent = apps.get_model('billing', 'Agent')
    JobTicket = apps.get_model('dispatch', 'JobTicket')
    DispatchRecord = apps.get_model('dispatch', 'DispatchRecord')
    MonitoringRecord = apps.get_model('dispatch', 'MonitoringRecord')

    agents_by_name = {a.name.lower().strip(): a for a in Agent.objects.all()}

    # 1. JobTicket
    for jt in JobTicket.objects.all():
        raw = (jt.sales_agent_raw or '').strip()
        matched = None
        if raw:
            matched = agents_by_name.get(raw.lower())
            if matched:
                jt.sales_agent = matched
                if getattr(matched, 'is_test_data', False):
                    jt.is_test_data = True
                print(f"[DATA MIGRATION] Linked JobTicket #{jt.id} ({jt.ticket_number}) '{raw}' -> Agent #{matched.id} ({matched.name})")
            else:
                print(f"[DATA MIGRATION WARNING] JobTicket #{jt.id} ({jt.ticket_number}) sales_agent_raw '{raw}' did NOT match any known Agent!")

        if jt.customer and getattr(jt.customer, 'is_test_data', False):
            jt.is_test_data = True
        jt.save()

    # 2. DispatchRecord
    for dr in DispatchRecord.objects.all():
        raw = (dr.sales_agent_raw or '').strip()
        matched = None
        if raw:
            matched = agents_by_name.get(raw.lower())
            if matched:
                dr.sales_agent = matched
                if getattr(matched, 'is_test_data', False):
                    dr.is_test_data = True
                print(f"[DATA MIGRATION] Linked DispatchRecord #{dr.id} '{raw}' -> Agent #{matched.id} ({matched.name})")
            else:
                print(f"[DATA MIGRATION WARNING] DispatchRecord #{dr.id} sales_agent_raw '{raw}' did NOT match any known Agent!")

        if dr.customer and getattr(dr.customer, 'is_test_data', False):
            dr.is_test_data = True
        dr.save()

    # 3. MonitoringRecord
    for mr in MonitoringRecord.objects.all():
        raw = (mr.sales_agent_raw or '').strip()
        matched = None
        if raw:
            matched = agents_by_name.get(raw.lower())
            if matched:
                mr.sales_agent = matched
                if getattr(matched, 'is_test_data', False):
                    mr.is_test_data = True
                print(f"[DATA MIGRATION] Linked MonitoringRecord #{mr.id} '{raw}' -> Agent #{matched.id} ({matched.name})")
            else:
                print(f"[DATA MIGRATION WARNING] MonitoringRecord #{mr.id} sales_agent_raw '{raw}' did NOT match any known Agent!")
        mr.save()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0051_agent_is_test_data'),
        ('dispatch', '0007_technician_is_available_alter_jobticket_status_and_more'),
    ]

    operations = [
        # Step 1: Rename old CharFields to raw
        migrations.RenameField(
            model_name='dispatchrecord',
            old_name='sales_agent',
            new_name='sales_agent_raw',
        ),
        migrations.RenameField(
            model_name='monitoringrecord',
            old_name='sales_agent',
            new_name='sales_agent_raw',
        ),
        migrations.RenameField(
            model_name='jobticket',
            old_name='sales_agent',
            new_name='sales_agent_raw',
        ),

        # Step 2: Add ForeignKey and is_test_data
        migrations.AddField(
            model_name='dispatchrecord',
            name='sales_agent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='dispatch_records',
                to='billing.agent'
            ),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='is_test_data',
            field=models.BooleanField(
                default=False,
                help_text='Flags test dispatch records'
            ),
        ),
        migrations.AddField(
            model_name='monitoringrecord',
            name='sales_agent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='monitoring_records',
                to='billing.agent'
            ),
        ),
        migrations.AddField(
            model_name='monitoringrecord',
            name='is_test_data',
            field=models.BooleanField(
                default=False,
                help_text='Flags test monitoring records'
            ),
        ),
        migrations.AddField(
            model_name='jobticket',
            name='sales_agent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='job_tickets',
                to='billing.agent'
            ),
        ),
        migrations.AddField(
            model_name='jobticket',
            name='is_test_data',
            field=models.BooleanField(
                default=False,
                help_text='Flags test job tickets'
            ),
        ),

        # Step 3: Run data migration
        migrations.RunPython(migrate_sales_agents_forward, reverse_code=migrations.RunPython.noop),

        # Step 4: Remove raw CharFields
        migrations.RemoveField(
            model_name='dispatchrecord',
            name='sales_agent_raw',
        ),
        migrations.RemoveField(
            model_name='monitoringrecord',
            name='sales_agent_raw',
        ),
        migrations.RemoveField(
            model_name='jobticket',
            name='sales_agent_raw',
        ),
    ]
