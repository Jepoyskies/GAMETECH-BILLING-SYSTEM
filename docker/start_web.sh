#!/bin/sh

echo "Starting Web server..."

python manage.py collectstatic --noinput
python manage.py migrate

exec gunicorn gametech_core.wsgi:application --bind 0.0.0.0:8000 --workers 4 --threads 4 --worker-class gthread --timeout 120 --max-requests 1000 --max-requests-jitter 50 --access-logfile - --error-logfile -