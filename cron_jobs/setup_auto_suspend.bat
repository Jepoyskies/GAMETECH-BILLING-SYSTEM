@echo off
REM Create a scheduled task to run Django auto_suspend every 5 minutes
set TASK_BAT="%~dp0run_auto_suspend.bat"
set TASK_NAME=DjangoAutoSuspend

schtasks /Create /TN "%TASK_NAME%" /TR %TASK_BAT% /SC minute /MO 5 /F

echo Scheduled task "%TASK_NAME%" created to run every 5 minutes.
pause
