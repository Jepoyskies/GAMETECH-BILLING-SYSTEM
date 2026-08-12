@echo off
echo Setting up Gametech Billing System...
py -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
echo Setup complete.
pause
