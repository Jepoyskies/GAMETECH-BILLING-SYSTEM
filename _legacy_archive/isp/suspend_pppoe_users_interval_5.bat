@echo off
setlocal enableextensions

REM === CONFIG ===
set "URL=http://localhost/isp/suspend_pppoe_users.php"
set "LOG=C:\wamp64\logs\suspend_cron.log"

REM Ensure log directory exists
for %%D in ("%LOG%") do if not exist "%%~dpD" mkdir "%%~dpD"

echo.
echo ================== STARTING AUTO-SUSPEND LOOP ==================
echo Target URL: %URL%
echo Log file  : %LOG%
echo Interval  : 5 minutes
echo Close this window to stop.
echo.

:loop
set "HTTP="
echo [%date% %time%] Triggering suspend_expired... >> "%LOG%"
for /f "usebackq tokens=* delims=" %%H in (
    `curl -s -S -o NUL -w "HTTP=%%{http_code}" -X POST -d "action=suspend_expired" "%URL%" 2^>^> "%LOG%"`
) do set "HTTP=%%H"

if not defined HTTP (
    echo [%date% %time%] ERROR: No response from curl! >> "%LOG%"
) else (
    echo [%date% %time%] Result: %HTTP% >> "%LOG%"
)

REM Wait 300 seconds (5 minutes) before next run
timeout /t 300 /nobreak >NUL
goto loop
