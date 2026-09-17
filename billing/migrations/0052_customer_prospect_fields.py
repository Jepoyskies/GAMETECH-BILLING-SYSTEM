# Generated for Customer prospect fields (installation date, ID type/number, payment method)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0051_agent_is_test_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='preferred_installation_date',
            field=models.DateField(blank=True, help_text='Requested date for initial installation', null=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='id_type',
            field=models.CharField(blank=True, help_text="e.g. UMID, PhilSys, Driver's License, Passport", max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='id_number',
            field=models.CharField(blank=True, help_text='ID card serial or identification number', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='preferred_payment_method',
            field=models.CharField(
                choices=[('cash', 'Cash on Hand'), ('gcash', 'Direct GCash')],
                default='cash',
                help_text='Payment method chosen during prospect application',
                max_length=20,
            ),
        ),
    ]
