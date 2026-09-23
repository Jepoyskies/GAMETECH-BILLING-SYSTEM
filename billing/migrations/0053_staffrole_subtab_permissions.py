# Generated for StaffRole subtab permissions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0052_customer_prospect_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffrole',
            name='subtab_permissions',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
