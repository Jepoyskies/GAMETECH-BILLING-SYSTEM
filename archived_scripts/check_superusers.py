from django.contrib.auth.models import User

superusers = User.objects.filter(is_superuser=True)
print(f"Total Superusers: {superusers.count()}")
print("-" * 30)
for u in superusers:
    print(f"Username: {u.username}, Email: {u.email}, Active: {u.is_active}, Last Login: {u.last_login}")
