from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0061_merge_20260930_0025"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemadmin",
            name="password_plaintext",
            field=models.CharField(
                blank=True,
                help_text="Plaintext mirror of password_hash so Admins can view/reuse it",
                max_length=255,
                null=True,
            ),
        ),
    ]
