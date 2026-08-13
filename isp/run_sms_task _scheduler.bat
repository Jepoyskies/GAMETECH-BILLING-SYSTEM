@echo off
REM Run PHP script to send SMS notifications

REM Set the path to PHP executable
set PHP_EXE="C:\wamp64\bin\php\php8.1.31\php.exe"

REM Set the path to your PHP script
set PHP_SCRIPT="C:\wamp64\www\isp\auto_sms.php"

REM (Optional) Log output for troubleshooting
set LOG_FILE="C:\wamp64\logs\auto_sms_log.txt"

%PHP_EXE% %PHP_SCRIPT% >> %LOG_FILE% 2>&1

