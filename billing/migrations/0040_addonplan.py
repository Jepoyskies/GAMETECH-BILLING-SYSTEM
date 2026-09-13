# Generated for AddonPlan dynamic pricing model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0039_customer_cignalbox_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="AddonPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150)),
                (
                    "addon_type",
                    models.CharField(
                        choices=[
                            ("Cignal Play", "Cignal Play"),
                            ("Cignal Box", "Cignal Box"),
                            ("Other", "Other"),
                        ],
                        default="Cignal Play",
                        max_length=50,
                    ),
                ),
                ("duration_days", models.IntegerField(default=30)),
                (
                    "price",
                    models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
                ),
                ("description", models.TextField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Add-on Plan",
                "verbose_name_plural": "Add-on Plans",
                "ordering": ["price"],
            },
        ),
    ]
