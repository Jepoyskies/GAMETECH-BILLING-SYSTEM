# Generated manually for Payment is_test_data field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0049_commissiontransaction_is_test_data_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='is_test_data',
            field=models.BooleanField(default=False, help_text='Flags test payments to exclude from revenue'),
        ),
    ]
