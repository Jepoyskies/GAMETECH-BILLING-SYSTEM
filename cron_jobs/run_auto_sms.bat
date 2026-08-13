@echo off
REM Run Django auto_sms management command
cd ..
.\venv\Scripts\python manage.py auto_sms >> logs\auto_sms_log.txt 2>&1
