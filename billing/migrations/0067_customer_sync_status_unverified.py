from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0066_customer_legacy_review_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customer",
            name="sync_status",
            field=models.CharField(
                choices=[
                    ("Unverified", "Unverified"),
                    ("Pending", "Pending Push"),
                    ("Synced", "Synced"),
                    ("Failed", "Failed"),
                    ("Blocked", "Blocked"),
                ],
                default="Unverified",
                max_length=20,
            ),
        ),
        # The legacy import hardcoded sync_status="Synced" on every row, so all
        # 2,041 imported accounts claimed to be verified against a router when
        # none of them ever had been. Reset to the honest default. Rows the
        # system itself marked Failed/Blocked are left alone -- those carry real
        # information.
        migrations.RunSQL(
            sql=(
                "UPDATE billing_customer SET sync_status = 'Unverified' "
                "WHERE sync_status = 'Synced';"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
