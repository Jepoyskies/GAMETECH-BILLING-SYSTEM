@echo off
REM Run PHP script to auto suspend expired PPPoE users

REM Set the path to PHP executable (no quotes here)
set PHP_EXE=C:\wamp64\bin\php\php8.1.31\php.exe

REM Set the path to your PHP script (no quotes here)
set PHP_SCRIPT=C:\wamp64\www\isp\auto_suspend_pppoe_users.php

REM (Optional) Log output for troubleshooting
set LOG_FILE=C:\wamp64\logs\suspend_pppoe_log.txt

REM Now run the script (quotes only around path with spaces, not variables)
"%PHP_EXE%" "%PHP_SCRIPT%" >> "%LOG_FILE%" 2>&1
