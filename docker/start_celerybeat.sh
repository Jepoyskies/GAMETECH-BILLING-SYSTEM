#!/bin/sh

echo "Starting Celery beat..."
celery -A gametech_core beat -l info
