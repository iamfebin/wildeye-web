@echo off
setlocal enabledelayedexpansion
title WildEye Platform Launcher

echo ==================================================
echo 🐾 Starting WildEye Platform (Windows)
echo ==================================================

rem Navigate to script directory (root of repository)
cd /d "%~dp0"

rem 1. Environment Configuration Check
if not exist ".env" (
    if exist ".env.example" (
        echo [!] .env file not found. Creating from .env.example...
        copy .env.example .env >nul
    )
)

rem 2. Activate Python Virtual Environment
set "VENV_DIR=%~dp0venv"

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [1/4] Activating virtual environment...
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo [1/4] Virtual environment not found at %VENV_DIR%
    echo [!] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Please ensure Python is installed and added to PATH.
        pause
        exit /b 1
    )
    call "%VENV_DIR%\Scripts\activate.bat"
)

rem 3. Check & Install Dependencies
echo [2/4] Checking Python dependencies...
python -c "import django, rest_framework, pymysql, paho.mqtt, dotenv" >nul 2>&1
if errorlevel 1 (
    echo [!] Missing dependencies detected. Installing from requirements.txt...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
) else (
    echo [✓] Dependencies verified.
)

rem 4. Apply Database Migrations
echo [3/4] Applying Django database migrations...
python backend\manage.py migrate
if errorlevel 1 (
    echo [WARNING] Database migration failed. Please ensure MySQL is running and database configuration in .env is correct.
)

rem 5. Start Background MQTT Subscriber and Django Server
echo [4/4] Starting Background MQTT Subscriber ^& Django Web Portal...
echo --------------------------------------------------

rem Start MQTT subscriber in background
echo [✓] Launching Background MQTT Subscriber Daemon...
start "WildEye MQTT Subscriber Daemon" /B python backend\manage.py run_mqtt_subscriber

rem Auto open browser after server initialization
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8000"

echo [✓] Launching Django Web Portal on http://127.0.0.1:8000
echo Press Ctrl+C in this window to stop the Django server.
echo --------------------------------------------------
python backend\manage.py runserver 0.0.0.0:8000

endlocal
