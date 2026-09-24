from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dispatch', '0012_jobticket_arrival_coords_timer_correction'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobticket',
            name='is_flagged',
            field=models.BooleanField(default=False, help_text='Flagged for manual administrative review'),
        ),
        migrations.AlterField(
            model_name='ticketbouncehistory',
            name='bounce_type',
            field=models.CharField(
                choices=[
                    ('revisit', 'Revisit with new timer'),
                    ('correct_report', 'Correct the report'),
                    ('admin_to_dispatch', 'Admin returned to Dispatch QA'),
                ],
                default='correct_report',
                max_length=50,
            ),
        ),
    ]
