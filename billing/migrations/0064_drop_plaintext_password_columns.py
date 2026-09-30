from django.db import migrations


class Migration(migrations.Migration):
    """
    Drops the two plaintext password mirror columns.

    `SystemAdmin.password_plaintext` and `Customer.portal_password_plaintext`
    were read-back mirrors so staff could view an existing password instead of
    resetting it. Both authentication paths already used the PBKDF2 hash, and
    the customer reset flow already SMSes the temp password to the subscriber,
    so the mirrors were redundant as well as a liability: a database dump or
    read-only SQL access yielded every staff login and every subscriber's
    portal login in clear text.

    Passwords are now hash-only. Staff reset a forgotten password through the
    existing Override Password field; subscribers use Forgot Password.
    """

    dependencies = [
        ("billing", "0063_customer_portal_password_plaintext"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="customer",
            name="portal_password_plaintext",
        ),
        migrations.RemoveField(
            model_name="systemadmin",
            name="password_plaintext",
        ),
    ]