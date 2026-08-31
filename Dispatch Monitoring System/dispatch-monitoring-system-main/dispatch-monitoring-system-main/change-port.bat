@echo off
setlocal enabledelayedexpansion
title Dispatch System - Change IP / Port

cd /d "%~dp0"

if not exist "backend\.env" (
    echo [ERROR] backend\.env not found. Run install.bat first.
    pause
    exit /b 1
)

echo =========================================
echo  Dispatch Monitoring System
echo   Change IP Address / Port
echo =========================================
echo(

:: -- Detect current values -----------------------
for /f "tokens=1,* delims==" %%a in ('findstr /b "PORT=" backend\.env 2^>nul') do set "CURRENT_PORT=%%b"
for /f "tokens=1,* delims==" %%a in ('findstr /b "SERVER_IP=" backend\.env 2^>nul') do set "CURRENT_IP=%%b"

echo  Current IP  : !CURRENT_IP!
echo  Current Port: !CURRENT_PORT!
echo(

:: -- Ask what to change -------------------------
:askMode
echo What do you want to change?
echo  [1] IP address only
echo  [2] Port number only
echo  [3] Both IP and Port
echo(
set /p CHOICE="Choice (1/2/3): "
if "!CHOICE!"=="1" (set CHANGE_IP=1&set CHANGE_PORT=0&goto proceed)
if "!CHOICE!"=="2" (set CHANGE_IP=0&set CHANGE_PORT=1&goto proceed)
if "!CHOICE!"=="3" (set CHANGE_IP=1&set CHANGE_PORT=1&goto proceed)
echo [ERROR] Invalid choice. Enter 1, 2, or 3.
goto askMode

:proceed

:: -- Ask for new IP -----------------------------
if "!CHANGE_IP!"=="1" (
    :askIP
    set /p NEW_IP="Enter new IP address: "
    if "!NEW_IP!"=="" (
        echo [ERROR] IP is required.
        goto askIP
    )
    echo !NEW_IP!| findstr /r "^[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*$" >nul
    if !errorLevel! neq 0 (
        echo [ERROR] Invalid IP format. Use xxx.xxx.xxx.xxx
        goto askIP
    )
    echo [OK] New IP: !NEW_IP!
)

:: -- Ask for new Port ---------------------------
if "!CHANGE_PORT!"=="1" (
    :askPort
    set /p NEW_PORT="Enter new port number: "
    if "!NEW_PORT!"=="" (
        echo [ERROR] Port is required.
        goto askPort
    )
    set "test=!NEW_PORT!"
    if not "!test:~5!"=="" (
        echo [ERROR] Port cannot exceed 5 digits.
        goto askPort
    )
    set /a "PORT_NUM=!NEW_PORT!" 2>nul
    if "!PORT_NUM!"=="0" (
        echo [ERROR] Port must be a number.
        goto askPort
    )
    if !PORT_NUM! lss 1 (
        echo [ERROR] Port must be between 1 and 65535.
        goto askPort
    )
    if !PORT_NUM! gtr 65535 (
        echo [ERROR] Port must be between 1 and 65535.
        goto askPort
    )
    echo [OK] New port: !NEW_PORT!
)

set "FINAL_IP=!CURRENT_IP!"
if "!CHANGE_IP!"=="1" set "FINAL_IP=!NEW_IP!"
set "FINAL_PORT=!CURRENT_PORT!"
if "!CHANGE_PORT!"=="1" set "FINAL_PORT=!NEW_PORT!"

echo(
echo Updating files...

:: -- Update IP in backend\.env ---------------------
if "!CHANGE_IP!"=="1" (
    powershell -Command "$r = Get-Content 'backend\.env'; $r = $r -replace '(?<=^SERVER_IP=).*', '!NEW_IP!'; $r | Set-Content 'backend\.env' -Encoding UTF8"
    if !errorLevel! equ 0 ( echo [OK] IP updated in backend\.env ) else ( echo [WARN] Failed to update backend\.env )
)

:: -- Update PORT in backend\.env ----------------
if "!CHANGE_PORT!"=="1" (
    powershell -Command "$c = Get-Content 'backend\.env'; $c = $c -replace '^PORT=\d+', 'PORT=!NEW_PORT!'; $c | Set-Content 'backend\.env' -Encoding UTF8"
    if !errorLevel! equ 0 ( echo [OK] PORT updated in backend\.env ) else ( echo [WARN] Failed to update PORT )
)

:: -- Update CORS_ORIGINS in backend\.env ---------
if "!CHANGE_IP!!CHANGE_PORT!" neq "00" (
    powershell -Command "$c = Get-Content 'backend\.env'; $c = $c -replace '^CORS_ORIGINS=.*', 'CORS_ORIGINS=http://!FINAL_IP!:!FINAL_PORT!'; $c | Set-Content 'backend\.env' -Encoding UTF8"
)

:: -- Verify CORS_ORIGINS actually changed --------
set "NEW_CORS="
for /f "tokens=1,* delims==" %%a in ('findstr /b "CORS_ORIGINS=" backend\.env 2^>nul') do set "NEW_CORS=%%b"

if "!CHANGE_IP!!CHANGE_PORT!" neq "00" (
    if "!NEW_CORS!"=="http://!FINAL_IP!:!FINAL_PORT!" (
        echo [OK] CORS_ORIGINS updated in backend\.env -^> !NEW_CORS!
    ) else (
        echo [WARN] Failed to update CORS_ORIGINS ^(current value: !NEW_CORS!^)
    )
)

:: -- Summary -------------------------------------
echo(
echo ----------- Summary -----------
if "!CHANGE_IP!"=="1" (
    for /f "tokens=1,* delims==" %%a in ('findstr /b "SERVER_IP=" backend\.env 2^>nul') do echo    IP : !CURRENT_IP! -^> %%b
)
if "!CHANGE_PORT!"=="1" (
    for /f "tokens=1,* delims==" %%a in ('findstr /b "PORT=" backend\.env 2^>nul') do echo    Port: !CURRENT_PORT! -^> %%b
)
if "!CHANGE_IP!!CHANGE_PORT!" neq "00" (
    echo    CORS: !NEW_CORS!
)

:: -- Restart PM2 ---------------------------------
echo(
set /p RESTART_PM2="Restart PM2 now? (Y/n): "
if /i not "!RESTART_PM2!"=="n" (
    where pm2 >nul 2>&1
    if !errorLevel! equ 0 (
        call pm2 restart dispatch-backend
        echo [OK] PM2 restarted
    ) else (
        echo [SKIP] PM2 not found. Restart manually.
    )
)

echo(
echo =========================================
echo  Done!
echo =========================================
echo(
pause