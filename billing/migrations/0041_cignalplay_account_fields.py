# Generated for CignalPlay multiple subscriptions and flexible payment tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0040_addonplan"),
    ]

    operations = [
        migrations.AddField(
            model_name="cignalplay",
            name="account_name",
            field=models.CharField(
                blank=True, help_text="e.g. Living Room TV", max_length=150, null=True
            ),
        ),
        migrations.AddField(
            model_name="cignalplay",
            name="account_number",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="cignalplay",
            name="addon_type",
            field=models.CharField(default="Cignal Play", max_length=50),
        ),
        migrations.AddField(
            model_name="cignalplay",
            name="amount_paid",
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name="cignalplay",
            name="expiration_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
