# Generated migration for CignalPlay cancellation and soft-delete fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0044_cignalplay_hardware_payment_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cignalplay",
            name="is_cancelled",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="cignalplay",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cignalplay",
            name="cancelled_by",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
