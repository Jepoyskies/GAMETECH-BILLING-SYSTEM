from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0065_staffrole_can_access_agents"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="legacy_reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="legacy_review_note",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
