@echo off
REM Create a scheduled task to run Django auto_sms every 5 minutes
set TASK_BAT="%~dp0run_auto_sms.bat"
set TASK_NAME=DjangoAutoSMS

schtasks /Create /TN "%TASK_NAME%" /TR %TASK_BAT% /SC minute /MO 5 /F

echo Scheduled task "%TASK_NAME%" created to run every 5 minutes.
pause
