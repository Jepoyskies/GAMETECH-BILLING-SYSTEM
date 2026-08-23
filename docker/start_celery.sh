#!/bin/sh

echo "Starting Celery worker..."
celery -A gametech_core worker -l info
