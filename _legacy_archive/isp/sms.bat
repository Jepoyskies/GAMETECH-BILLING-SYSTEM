@echo off
REM Change the following paths to your actual locations
set "PHP_PATH=C:\wamp64\bin\php\php8.2.0\php.exe"
set "SCRIPT_PATH=C:\wamp64\www\isp\auto_sms.php"
set "LOGFILE=C:\wamp64\logs\auto_sms.log"

REM Ensure log directory exists
for %%D in ("%LOGFILE%") do if not exist "%%~dpD" mkdir "%%~dpD"

REM Run the PHP script, append output to log
echo [%date% %time%] Running auto_sms.php >> "%LOGFILE%"
"%PHP_PATH%" "%SCRIPT_PATH%" >> "%LOGFILE%" 2>&1
echo [%date% %time%] Completed. >> "%LOGFILE%"
