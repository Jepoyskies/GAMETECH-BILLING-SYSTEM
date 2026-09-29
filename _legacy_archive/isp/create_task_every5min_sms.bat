@echo off
REM This script creates a scheduled task to run your auto_sms batch file every 5 minutes

REM Path to your batch file
set TASK_BAT="C:\wamp64\www\isp\run_sms_task _scheduler.bat"

REM Name of the scheduled task
set TASK_NAME=AutoSMSNotification

REM Schedule: every 5 minutes
schtasks /Create /TN "%TASK_NAME%" /TR %TASK_BAT% /SC minute /MO 5 /F

echo Scheduled task "%TASK_NAME%" created to run every 5 minutes.
pause
