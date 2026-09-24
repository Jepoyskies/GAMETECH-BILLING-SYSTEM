from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0057_phase3_1_updates'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='customer',
            options={'permissions': [
                ('add_existing_subscriber', 'Can add installed/existing subscriber with manual override'),
                ('change_customer_agent', 'Can change customer assigned sales agent'),
                ('import_router_subscribers', 'Can import subscribers from router sync or recovery'),
                ('bypass_customer_checklist', 'Can bypass customer onboarding checklist'),
            ]},
        ),
        migrations.AddField(
            model_name='customer',
            name='source',
            field=models.CharField(
                default='manual',
                help_text='Origin of subscriber record (e.g. manual, agent, router_sync, recovery)',
                max_length=50
            ),
        ),
    ]
