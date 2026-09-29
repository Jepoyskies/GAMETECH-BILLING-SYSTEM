from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0058_phase3_2_guards_and_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customer",
            name="expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
