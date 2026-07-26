@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM =============================================================
REM Solar Monitoring Framework - Windows Installation Script
REM =============================================================

REM Always run from this script's directory (repo root)
cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Could not change to the installer directory.
    pause
    exit /b 1
)

echo ==========================================
echo Solar Monitoring Framework Installation
echo ==========================================
echo.
echo [INFO] Install directory: %CD%
echo.

REM -------------------------------------------------------------
REM Locate a usable Python 3.9+ interpreter
REM Prefer "python", then Windows launcher "py -3"
REM -------------------------------------------------------------
set "PYTHON_CMD="
set "PYTHON_ARGS="

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py"
        set "PYTHON_ARGS=-3"
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.9 or newer from https://www.python.org/downloads/
    echo During setup, enable "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

echo [STEP] Checking Python version...
%PYTHON_CMD% %PYTHON_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    for /f "tokens=*" %%i in ('%PYTHON_CMD% %PYTHON_ARGS% -c "import sys; print(sys.version.split()[0])" 2^>^&1') do set "PYTHON_VERSION=%%i"
    echo [ERROR] Python !PYTHON_VERSION! found, but Python 3.9 or newer is required.
    echo Download a current installer from https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% %PYTHON_ARGS% -c "import sys; print(sys.version.split()[0])" 2^>^&1') do set "PYTHON_VERSION=%%i"
echo [INFO] Using: %PYTHON_CMD% %PYTHON_ARGS%  ^(Python %PYTHON_VERSION%^)
echo.

REM -------------------------------------------------------------
REM Virtual environment
REM -------------------------------------------------------------
echo [STEP] Creating Python virtual environment...
if exist "venv\Scripts\python.exe" (
    echo [WARNING] Existing venv found. Removing it for a clean install...
    rmdir /s /q venv
    if exist venv (
        echo [ERROR] Could not remove old venv. Close any app using it and retry.
        pause
        exit /b 1
    )
)

%PYTHON_CMD% %PYTHON_ARGS% -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    echo Tip: reinstall Python and ensure "pip" / "venv" are included.
    pause
    exit /b 1
)
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv was created but venv\Scripts\python.exe is missing.
    pause
    exit /b 1
)
echo [INFO] Virtual environment created
echo.

REM Always use the venv interpreter explicitly (more reliable than activate alone)
set "VENV_PY=%CD%\venv\Scripts\python.exe"

REM -------------------------------------------------------------
REM Dependencies
REM -------------------------------------------------------------
echo [STEP] Upgrading pip / setuptools / wheel...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip tooling.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found in %CD%
    pause
    exit /b 1
)

echo [STEP] Installing Python dependencies from requirements.txt...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install dependencies.
    echo If you see errors about greenlet / compiling, install
    echo "Microsoft C++ Build Tools" or use a matching Python wheel build,
    echo then re-run this installer.
    echo.
    pause
    exit /b 1
)
echo [INFO] Dependencies installed
echo.

REM -------------------------------------------------------------
REM Smoke-test critical imports
REM -------------------------------------------------------------
echo [STEP] Verifying critical modules can import...
"%VENV_PY%" -c "import eventlet, flask, flask_socketio, pymodbus, serial, paho.mqtt.client, packaging, ping3, tinytuya, curses; print('OK')"
if errorlevel 1 (
    echo [ERROR] Dependency import check failed.
    echo Re-run install.bat, or manually: venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
echo [INFO] Import check passed
echo.

REM -------------------------------------------------------------
REM Configuration
REM -------------------------------------------------------------
echo [STEP] Setting up configuration...
if not exist "config.ini" (
    if exist "config.ini.example" (
        copy /y "config.ini.example" "config.ini" >nul
        echo [INFO] Created config.ini from config.ini.example
        echo [INFO] On first run you can use the setup wizard, or edit config.ini manually.
    ) else (
        echo [ERROR] config.ini.example not found!
        pause
        exit /b 1
    )
) else (
    echo [INFO] config.ini already exists - leaving it unchanged
)
echo.

REM -------------------------------------------------------------
REM Startup helpers (checked into the repo; refresh copy message)
REM -------------------------------------------------------------
echo [STEP] Checking startup scripts...
for %%F in (start_solar_monitoring.bat start_with_restart.bat run_setup_wizard.bat) do (
    if exist "%%F" (
        echo [INFO] Found %%F
    ) else (
        echo [WARNING] %%F is missing from the install folder.
        echo           Re-download/copy it from the project repository.
    )
)
echo.

echo ==========================================
echo [INFO] Installation completed successfully!
echo ==========================================
echo.
echo [INFO] Next steps:
echo   1. Configure devices:
echo        - Easy:   run_setup_wizard.bat
echo        - Manual: edit config.ini
echo   2. Start once:     start_solar_monitoring.bat
echo   3. Auto-restart:   start_with_restart.bat
echo   4. Open dashboard: http://localhost:8081
echo.
echo [TIP] Keep this window's folder as your install location.
echo       Do not delete the venv folder after install.
echo.
pause
endlocal
exit /b 0
