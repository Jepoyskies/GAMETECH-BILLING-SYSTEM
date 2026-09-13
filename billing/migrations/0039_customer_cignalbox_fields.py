# Generated manually for Cignal Box integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0038_alter_customer_created_at_alter_customer_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="cignalbox_no",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="cignalbox_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="cignalbox_adjustedby",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
