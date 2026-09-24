from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('billing', '0056_checklistconfirmation_applicant_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='customer',
            options={'permissions': [
                ('add_existing_subscriber', 'Can add installed/existing subscriber with manual override'),
                ('change_customer_agent', 'Can change customer assigned sales agent'),
            ]},
        ),
        migrations.CreateModel(
            name='ChecklistPolicySetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=1, help_text='Policy version number')),
                ('item_free_install_text', models.CharField(default='Free installation', max_length=255)),
                ('item_specific_plan_template', models.CharField(default='Their plan: {plan_name} (₱{price}/month)', help_text='Template for dynamic plan display', max_length=255)),
                ('item_no_lockin_text', models.CharField(default='No lock-in period', max_length=255)),
                ('item_staggered_agent_text', models.CharField(default='Staggered payments (3-day, 15-day payments): Not available for 60 days from your first payment', max_length=255)),
                ('item_staggered_walkin_text', models.CharField(default='Staggered payments (3-day, 15-day payments): Available', max_length=255)),
                ('item_same_day_repair_text', models.CharField(default='Repair within the day', max_length=255)),
                ('item_rebates_24h_text', models.CharField(default='Rebates within 24 hours', max_length=255)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-version'],
            },
        ),
        migrations.AddField(
            model_name='prospect',
            name='source',
            field=models.CharField(choices=[('agent_portal', 'Agent Portal'), ('staff_on_behalf', 'Staff on Agent Behalf'), ('direct', 'Direct')], default='agent_portal', max_length=50),
        ),
        migrations.AddField(
            model_name='prospect',
            name='reopened_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='prospect',
            name='reopened_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reopened_prospects', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='prospect',
            name='reopen_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='checklistconfirmation',
            name='policy_version',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='checklistconfirmation',
            name='method',
            field=models.CharField(choices=[('in_person', 'In-Person (Walk-In)'), ('phone', 'Phone Call')], default='in_person', max_length=20),
        ),
    ]
