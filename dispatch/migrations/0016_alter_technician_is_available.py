from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dispatch', '0015_alter_monitoringrecord_dispatch'),
    ]

    operations = [
        migrations.AlterField(
            model_name='technician',
            name='is_available',
            field=models.BooleanField(default=True, help_text='Manual duty-status hint shown in the roster. Does NOT restrict assignment.'),
        ),
    ]
