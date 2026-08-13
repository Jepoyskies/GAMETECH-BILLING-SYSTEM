@echo off
REM Run Django auto_suspend management command
cd ..
.\venv\Scripts\python manage.py auto_suspend >> logs\auto_suspend_log.txt 2>&1
