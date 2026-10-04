from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0068_payment_legacy_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("auto_sync_routers", models.BooleanField(default=False, help_text="Automatically push new customers to their MikroTik router upon creation.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "System Configuration",
                "verbose_name_plural": "System Configuration",
            },
        ),
    ]
