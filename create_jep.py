from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.filter(username='Jep').delete()
User.objects.create_superuser('Jep', 'jep@example.com', '1234')
