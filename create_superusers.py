from django.contrib.auth.models import User

users = [
    ('Jep', 'jep@gametech.com', '1234'),
    ('Jill', 'jill@gametech.com', '1234'),
    ('Admin', 'admin@gametech.com', '1234'),
]

for username, email, password in users:
    User.objects.filter(username=username).delete()
    u = User.objects.create_superuser(username, email, password)
    print(f"Created superuser: {u.username}")

print("Done!")
