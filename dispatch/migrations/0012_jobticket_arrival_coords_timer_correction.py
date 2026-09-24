import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dispatch', '0011_alter_jobticket_options_jobticket_admin_approved_at_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='jobticket',
            name='arrival_latitude',
            field=models.FloatField(blank=True, help_text='GPS latitude recorded upon arrival', null=True),
        ),
        migrations.AddField(
            model_name='jobticket',
            name='arrival_longitude',
            field=models.FloatField(blank=True, help_text='GPS longitude recorded upon arrival', null=True),
        ),
        migrations.AddField(
            model_name='jobticket',
            name='timer_corrected_at',
            field=models.DateTimeField(blank=True, help_text='When dispatcher corrected timer', null=True),
        ),
        migrations.AddField(
            model_name='jobticket',
            name='timer_corrected_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='timer_corrected_tickets', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='jobticket',
            name='timer_correction_reason',
            field=models.TextField(blank=True, help_text='Mandatory reason for manual timer adjustment', null=True),
        ),
    ]
