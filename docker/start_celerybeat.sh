#!/bin/sh

echo "Starting Celery Beat..."
celery -A gametech_core beat -l info
