# Generated for Phase 1: Security Hardening & Password Hashing
from django.db import migrations, models
from django.contrib.auth.hashers import make_password


def migrate_plaintext_passwords_to_hashes(apps, schema_editor):
    Customer = apps.get_model('billing', 'Customer')
    updated = 0
    for customer in Customer.objects.all():
        if customer.portal_password and not customer.portal_password_hash:
            customer.portal_password_hash = make_password(customer.portal_password)
            customer.portal_password = None
            customer.save(update_fields=['portal_password_hash', 'portal_password'])
            updated += 1
        elif customer.portal_password and customer.portal_password_hash:
            # Hash already exists, blank the plaintext
            customer.portal_password = None
            customer.save(update_fields=['portal_password'])


def reverse_passwords(apps, schema_editor):
    # One-way migration for security: cannot reverse secure hashes back to plaintext
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0053_staffrole_subtab_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='portal_password_hash',
            field=models.CharField(
                blank=True,
                help_text='PBKDF2/Argon2 secure password hash for customer portal',
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='temp_password_created_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Timestamp when temporary password was generated (valid 7 days)',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='customer',
            name='portal_password',
            field=models.CharField(
                blank=True,
                help_text='Legacy field - blanked after migration to portal_password_hash',
                max_length=50,
                null=True,
            ),
        ),
        migrations.RunPython(
            migrate_plaintext_passwords_to_hashes,
            reverse_code=reverse_passwords,
        ),
    ]
