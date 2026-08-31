@echo off
setlocal enabledelayedexpansion
title Dispatch System Installer

cd /d "%~dp0"
set PROJECT_ROOT=%CD%

echo =========================================
echo  Dispatch Monitoring System - Installer
echo =========================================
echo(

:: -- Check admin rights -----------------------------
net session >nul 2>&1
if !errorLevel! neq 0 (
    echo [ERROR] Run this installer as Administrator.
    echo         Right-click ^> "Run as administrator"
    pause
    exit /b 1
)

:: -- Check Node.js ----------------------------------
where node >nul 2>&1
if !errorLevel! neq 0 (
    echo [ERROR] Node.js is not installed.
    echo         Download v20 LTS from: https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=1" %%v in ('node -v') do echo [OK] Node.js %%v

:: -- Check npm --------------------------------------
where npm >nul 2>&1
if !errorLevel! neq 0 (
    echo [ERROR] npm not found - should be bundled with Node.js.
    echo         Reinstall Node.js from: https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=1" %%v in ('npm -v') do echo [OK] npm %%v

:: -- Check PostgreSQL ------------------------------
where psql >nul 2>&1
if !errorLevel! neq 0 (
    echo [ERROR] PostgreSQL CLI not found in PATH.
    echo         Install PostgreSQL 16 from: https://www.postgresql.org/download/
    echo         Make sure to include "Command Line Tools" during install.
    pause
    exit /b 1
)
for /f "tokens=1,2" %%v in ('psql --version') do echo [OK] PostgreSQL %%w

:: -- Detect PostgreSQL tool paths -------------------
for /f "tokens=*" %%i in ('where pg_dump 2^>nul') do set PG_DUMP_PATH=%%i
for /f "tokens=*" %%i in ('where pg_restore 2^>nul') do set PG_RESTORE_PATH=%%i
for /f "tokens=*" %%i in ('where psql 2^>nul') do set PSQL_PATH=%%i

:: -- Database setup ---------------------------------
echo(
echo [1/7] Database Setup
echo ---------------------

set /p POSTGRES_PASSWORD="Enter PostgreSQL admin password (postgres user): "

echo Verifying PostgreSQL admin credentials...
set PGPASSWORD=!POSTGRES_PASSWORD!
psql -U postgres -c "SELECT 1;" >nul 2>nul
if !errorLevel! neq 0 (
    echo [ERROR] Could not authenticate as 'postgres'. Wrong password or PostgreSQL not running.
    set PGPASSWORD=
    pause
    exit /b 1
)
echo [OK] PostgreSQL admin credentials verified

:: Check if user and database already exist
set "USER_EXISTS=0"
set "DB_EXISTS=0"
for /f "tokens=*" %%i in ('psql -U postgres -t -A -c "SELECT 1 FROM pg_roles WHERE rolname='dispatch';" 2^>nul') do set "USER_EXISTS=%%i"
for /f "tokens=*" %%i in ('psql -U postgres -t -A -c "SELECT 1 FROM pg_database WHERE datname='dispatch_db';" 2^>nul') do set "DB_EXISTS=%%i"

set "BOTH_EXIST=0"
if "!USER_EXISTS!"=="1" if "!DB_EXISTS!"=="1" set "BOTH_EXIST=1"

if "!BOTH_EXIST!"=="1" (
    echo [OK] User 'dispatch' and database 'dispatch_db' already exist
    echo(
    set /p DB_PASSWORD="Enter password for 'dispatch' user: "
    if "!DB_PASSWORD!"=="" (
        echo [ERROR] Password is required.
        set PGPASSWORD=
        pause
        exit /b 1
    )
    set PGPASSWORD=!DB_PASSWORD!
    psql -U dispatch -d dispatch_db -c "SELECT 1;" >nul 2>nul
    if !errorLevel! neq 0 (
        echo [ERROR] Could not connect as 'dispatch'. Wrong password.
        set PGPASSWORD=
        pause
        exit /b 1
    )
    set PGPASSWORD=
    echo [OK] Database connection verified
) else (
    echo [INFO] Setting up database for the first time...
    set /p DB_PASSWORD="Enter password for 'dispatch' user (default: dispatch123): "
    if "!DB_PASSWORD!"=="" set DB_PASSWORD=dispatch123

    echo Creating database user and database...
    set PGPASSWORD=!POSTGRES_PASSWORD!
    psql -U postgres -c "CREATE USER dispatch WITH PASSWORD '!DB_PASSWORD!';" 2>nul
    psql -U postgres -c "CREATE DATABASE dispatch_db OWNER dispatch;" 2>nul
    psql -U postgres -d dispatch_db -c "GRANT ALL ON SCHEMA public TO dispatch;" 2>nul
    psql -U postgres -d dispatch_db -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dispatch;" 2>nul
    psql -U postgres -d dispatch_db -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dispatch;" 2>nul
    psql -U postgres -d dispatch_db -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO dispatch;" 2>nul
    psql -U postgres -d dispatch_db -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO dispatch;" 2>nul
    set PGPASSWORD=
    echo [OK] Database ready
)

:: -- Create .env files ------------------------------
echo(
echo [2/7] Configuration
echo ---------------------

:: Get local IP
set "LOCAL_IP="
for /f %%i in ('powershell -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' }).IPAddress" 2^>nul') do if "!LOCAL_IP!"=="" set "LOCAL_IP=%%i"
if "!LOCAL_IP!"=="" (
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
        set "LINE=%%a"
        set "LINE=!LINE: =!"
        echo !LINE! | findstr /r "^169\.254\." >nul 2>&1
        if !errorLevel! neq 0 if "!LOCAL_IP!"=="" set "LOCAL_IP=!LINE!"
    )
)

if not "!LOCAL_IP!"=="" (
    echo Detected IP: !LOCAL_IP!
    set SERVER_IP=!LOCAL_IP!
) else (
    echo [WARN] Could not detect a valid IP automatically.
    echo         Open CMD and run: ipconfig
    echo         Find "IPv4 Address" and paste it below.
    set /p SERVER_IP="Enter your PC's IP address: "
    if "!SERVER_IP!"=="" (
        echo [ERROR] IP address is required. Aborting.
        goto :eof
    )
)

:: Generate JWT secret
for /f %%i in ('powershell -Command "[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))" 2^>nul') do set JWT_SECRET=%%i
if "!JWT_SECRET!"=="" set JWT_SECRET=dev-secret-change-me

:: -- Ask for web port ------------------------------
echo(
:askPort
set /p APP_PORT="Enter web dashboard port (default: 5502): "
if "!APP_PORT!"=="" set APP_PORT=5502
set "test=!APP_PORT!"
if not "!test:~5!"=="" (
    echo [ERROR] Port cannot exceed 5 digits.
    goto askPort
)
set /a "PORT_NUM=!APP_PORT!" 2>nul
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
set "APP_PORT=!PORT_NUM!"
echo [OK] Port set to !APP_PORT!

:: Backup directory
echo(
set /p BACKUP_DIR="Enter backup folder path (default: .\backups): "
if "!BACKUP_DIR!"=="" set BACKUP_DIR=%PROJECT_ROOT%\backups
if not exist "!BACKUP_DIR!" mkdir "!BACKUP_DIR!"
echo [OK] Backups will be saved to: !BACKUP_DIR!

:: Backend .env
(
echo DATABASE_URL=postgresql://dispatch:!DB_PASSWORD!@localhost:5432/dispatch_db
echo PORT=!APP_PORT!
echo NODE_ENV=production
echo JWT_SECRET=!JWT_SECRET!
echo JWT_EXPIRES_IN=8h
echo SERVER_IP=!SERVER_IP!
echo CORS_ORIGINS=http://!SERVER_IP!:!APP_PORT!
echo BACKUP_DIR=!BACKUP_DIR!
echo.
echo REM PM2 / local only
echo PG_DUMP_PATH=!PG_DUMP_PATH!
echo PG_RESTORE_PATH=!PG_RESTORE_PATH!
echo PSQL_PATH=!PSQL_PATH!
) > backend\.env
echo [OK] backend\.env created

:: -- Install dependencies --------------------------
echo(
echo [3/7] Installing Dependencies
echo ------------------------------
echo This may take a few minutes...

call npm install --audit=false
if !errorLevel! neq 0 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
)

cd backend
call npm install --audit=false
if !errorLevel! neq 0 (
    echo [ERROR] Backend install failed
    pause
    exit /b 1
)
cd ..

cd frontend
call npm install --audit=false
if !errorLevel! neq 0 (
    echo [ERROR] Frontend install failed
    pause
    exit /b 1
)
cd ..
echo [OK] Dependencies installed

:: -- Prisma generate ------------------------------
echo(
echo [4/7] Generating Prisma Client
echo --------------------------------
cd backend
call npx prisma generate
cd ..
if !errorLevel! neq 0 (
    echo [ERROR] Prisma generate failed
    pause
    exit /b 1
)
echo [OK] Prisma client generated

:: -- Build ----------------------------------------
echo(
echo [5/7] Building Application
echo ---------------------------
call npm run build
if !errorLevel! neq 0 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)
echo [OK] Build complete

:: -- Migrate & Seed --------------------------------
echo(
echo [6/7] Database Migrations ^& Seeds
echo -----------------------------------
cd backend
call npx prisma migrate deploy
cd ..
if !errorLevel! neq 0 (
    echo [ERROR] Database migration failed
    pause
    exit /b 1
)
node backend/dist/prisma/seedConfigOptions.js
echo [OK] Config options seeded

set /p RUN_ADMIN_SEED="Seed Super Admin account? (y/N): "
if /i "!RUN_ADMIN_SEED!"=="y" (
    node backend/dist/prisma/seedSuperAdmin.js
    if !errorLevel! neq 0 (
        echo [WARN] Super Admin seed failed
    ) else (
        echo [OK] Super Admin seed completed
    )
) else (
    echo [SKIP] Super Admin seed skipped
)
echo [OK] Database ready

:: -- PM2 Setup -------------------------------------
echo(
echo [7/7] PM2 Setup
echo -----------------

if not exist logs mkdir logs

call npm install -g pm2
if !errorLevel! neq 0 (
    echo [ERROR] Failed to install PM2 globally
    pause
    exit /b 1
)

call pm2 start ecosystem.config.js
call pm2 save

call npm install -g pm2-windows-startup
if !errorLevel! neq 0 (
    echo [WARN] Could not install pm2-windows-startup.
    echo         Run "npm install -g pm2-windows-startup" and "pm2-startup install" manually later.
) else (
    call pm2-startup install
    if !errorLevel! neq 0 (
        echo [WARN] Could not auto-register PM2 startup task.
        echo         Run "pm2-startup install" manually later if you want auto-start on reboot.
    ) else (
        echo [OK] PM2 startup task registered
    )
)

echo [OK] PM2 configured

:: -- Done ------------------------------------------
echo(
echo =========================================
echo  Installation Complete!
echo =========================================
echo(
echo  Access: http://!SERVER_IP!:!APP_PORT!
echo(
echo  pm2 status              - Check if running
echo  pm2 logs dispatch-backend - View logs
echo  pm2 restart all         - Restart app
echo(
pause