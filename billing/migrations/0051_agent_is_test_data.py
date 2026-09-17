# Generated manually for Agent is_test_data field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0050_payment_is_test_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='is_test_data',
            field=models.BooleanField(default=False, help_text='Flags test agents to safely ignore without hard-deleting'),
        ),
    ]
