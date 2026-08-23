#!/bin/sh

echo "Running migrations..."
python manage.py migrate

echo "Starting Django web server..."
python manage.py runserver 0.0.0.0:8000
