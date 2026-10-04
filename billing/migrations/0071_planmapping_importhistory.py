from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0070_merge_20261004"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanMapping",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("legacy_name", models.CharField(max_length=255, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="billing.subscriptionplan")),
            ],
            options={
                "ordering": ["legacy_name"],
            },
        ),
        migrations.CreateModel(
            name="ImportHistory",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("filename", models.CharField(max_length=255)),
                ("total_customers", models.IntegerField(default=0)),
                ("created", models.IntegerField(default=0)),
                ("updated", models.IntegerField(default=0)),
                ("missing_passwords", models.IntegerField(default=0)),
                ("zero_date_customers", models.IntegerField(default=0)),
                ("unmapped_statuses", models.JSONField(blank=True, default=dict)),
                ("plans_created", models.IntegerField(default=0)),
                ("unmapped_plans", models.JSONField(blank=True, default=list)),
                ("devices_created", models.JSONField(blank=True, default=list)),
                ("payments_seen", models.IntegerField(default=0)),
                ("payments_created", models.IntegerField(default=0)),
                ("payments_updated", models.IntegerField(default=0)),
                ("payments_orphaned", models.IntegerField(default=0)),
                ("payment_total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("dry_run", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "Import History",
                "verbose_name_plural": "Import History",
                "ordering": ["-timestamp"],
            },
        ),
    ]
