#!/bin/sh

echo "Starting Web server..."

python manage.py collectstatic --noinput
python manage.py migrate

exec gunicorn gametech_core.wsgi:application --bind 0.0.0.0:8000