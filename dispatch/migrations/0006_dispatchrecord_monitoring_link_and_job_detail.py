from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dispatch', '0005_dispatchrecord_alternate_contact_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='dispatchrecord',
            name='monitoring_record',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auto_dispatch_source', to='dispatch.monitoringrecord'),
        ),
        # Note: This migration was originally created with related_name='dispatch_record'
        # which clashed with MonitoringRecord.dispatch. Fixed to 'auto_dispatch_source'.
        # A merge migration (0014) was created on production to resolve the conflict.
        migrations.AddField(
            model_name='dispatchrecord',
            name='schedule_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='schedule_time',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='barangay_city',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='account_no',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='job_order',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='email_address',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='nap_port',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='cable_length',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='nap_reading',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='pole_number',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='plan_package',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='ont_modem_sn',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='signal_level',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='facility',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='house_reading',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='special_instruction',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='technician_remarks',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dispatchrecord',
            name='acknowledged_by',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
