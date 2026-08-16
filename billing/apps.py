from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'billing'

    def ready(self):
        import billing.signals  # noqa: F401

        # Monkey-patch Django User model to map .role to SystemAdmin
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        def get_user_role(self):
            if self.is_superuser:
                return 'Admin'
            try:
                from billing.models import SystemAdmin
                return SystemAdmin.objects.get(username=self.username).role
            except Exception:
                return 'Viewer'
                
        User.add_to_class('role', property(get_user_role))
