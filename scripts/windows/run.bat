@echo off
echo Starting Gametech Billing System...
call venv\Scripts\activate.bat
python manage.py runserver
pause
