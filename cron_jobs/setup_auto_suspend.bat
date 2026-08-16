@echo off
REM Create a scheduled task to run Django auto_suspend every hour
set TASK_BAT="%~dp0run_auto_suspend.bat"
set TASK_NAME=DjangoAutoSuspend

schtasks /Create /TN "%TASK_NAME%" /TR %TASK_BAT% /SC HOURLY /F

echo Scheduled task "%TASK_NAME%" created to run hourly.
pause
