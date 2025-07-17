@echo off
REM =============================================================
REM Solar Monitoring Framework - Windows Installation Script
REM =============================================================

echo ==========================================
echo Solar Monitoring Framework Installation
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.9 or newer from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [INFO] Python found - checking version...
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [INFO] Python version: %PYTHON_VERSION%

REM Create virtual environment
echo [STEP] Creating Python virtual environment...
if exist venv (
    echo [WARNING] Virtual environment already exists. Removing old one...
    rmdir /s /q venv
)

python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)
echo [INFO] Virtual environment created

REM Activate virtual environment and install dependencies
echo [STEP] Installing Python dependencies...
call venv\Scripts\activate.bat

REM Upgrade pip
python -m pip install --upgrade pip

REM Install requirements
if exist requirements.txt (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    echo [INFO] Dependencies installed successfully
) else (
    echo [ERROR] requirements.txt not found!
    pause
    exit /b 1
)

REM Setup configuration
echo [STEP] Setting up configuration...
if not exist config.ini (
    if exist config.ini.example (
        copy config.ini.example config.ini >nul
        echo [INFO] Created config.ini from example template
        echo [WARNING] Please edit config.ini with your device settings before running
    ) else (
        echo [ERROR] config.ini.example not found!
        pause
        exit /b 1
    )
) else (
    echo [INFO] config.ini already exists - skipping
)

REM Create startup script
echo [STEP] Creating startup script...
echo @echo off > start_solar_monitoring.bat
echo cd /d "%%~dp0" >> start_solar_monitoring.bat
echo call venv\Scripts\activate.bat >> start_solar_monitoring.bat
echo python main.py >> start_solar_monitoring.bat
echo pause >> start_solar_monitoring.bat

echo [INFO] Created start_solar_monitoring.bat

REM Create auto-restart script
echo [STEP] Creating auto-restart script...
echo @echo off > start_with_restart.bat
echo cd /d "%%~dp0" >> start_with_restart.bat
echo :loop >> start_with_restart.bat
echo echo Starting Solar Monitoring... >> start_with_restart.bat
echo call venv\Scripts\activate.bat >> start_with_restart.bat
echo python main.py >> start_with_restart.bat
echo echo Script exited with errorlevel %%errorlevel%%. Waiting 10 seconds before restart... >> start_with_restart.bat
echo timeout /t 10 /nobreak ^>nul >> start_with_restart.bat
echo goto loop >> start_with_restart.bat

echo [INFO] Created start_with_restart.bat

echo.
echo ==========================================
echo [INFO] Installation completed successfully!
echo ==========================================
echo.
echo [INFO] Next steps:
echo   1. Edit config.ini with your device settings
echo   2. Run: start_solar_monitoring.bat
echo   3. Access web dashboard at: http://localhost:8081
echo.
echo [WARNING] Make sure to configure your inverter and BMS settings in config.ini
echo.
echo Available startup options:
echo   - start_solar_monitoring.bat     (Run once)
echo   - start_with_restart.bat         (Auto-restart on crash)
echo.
pause