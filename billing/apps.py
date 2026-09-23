from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"

    def ready(self):
        import billing.signals  # noqa: F401

        # Monkey-patch Django User model to map .role to SystemAdmin
        from django.contrib.auth import get_user_model

        User = get_user_model()

        def get_user_role(self):
            if self.is_superuser:
                return "Admin"
            if hasattr(self, "agent_profile") and not self.is_staff:
                return "Agent"
            try:
                from billing.models import SystemAdmin

                return SystemAdmin.objects.get(username=self.username).role
            except Exception:
                return "Viewer"

        def get_role_perms(self):
            class AllSubtabsMap(dict):
                def __getitem__(self, item):
                    return True
                def __getattr__(self, item):
                    return True
                def get(self, item, default=True):
                    return True

            class NoneSubtabsMap(dict):
                def __getitem__(self, item):
                    return False
                def __getattr__(self, item):
                    return False
                def get(self, item, default=False):
                    return False

            class AllPerms:
                can_access_billing = True
                can_access_network_ops = True
                can_access_cignal_play = True
                can_access_dispatch = True
                can_access_administration = True

                def has_subtab_perm(self, module, subtab):
                    return True

                @property
                def subtabs(self):
                    return AllSubtabsMap()

            class DefaultPerms:
                can_access_billing = False
                can_access_network_ops = False
                can_access_cignal_play = False
                can_access_dispatch = False
                can_access_administration = False

                def has_subtab_perm(self, module, subtab):
                    return False

                @property
                def subtabs(self):
                    return NoneSubtabsMap()

            if hasattr(self, "agent_profile") and not self.is_staff:
                return DefaultPerms()

            if self.is_superuser or self.role == "Admin":
                return AllPerms()

            try:
                from billing.models import StaffRole
                return StaffRole.objects.get(name=self.role)
            except Exception:
                return DefaultPerms()

        User.add_to_class("role", property(get_user_role))
        User.add_to_class("role_perms", property(get_role_perms))
