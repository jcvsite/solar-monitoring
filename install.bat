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
echo [INFO] Recommended Python: 3.11 or 3.12 from https://www.python.org/downloads/
echo [INFO] Supported: Python 3.9+ ^(including 3.14 with current requirements^)
echo.

REM -------------------------------------------------------------
REM Locate a real Python 3.9+ interpreter
REM Prefer: 3.12/3.11 (smoothest wheels), then other py -3.x, then python.exe
REM Skip the Windows Store "python" stub that is not a real install.
REM -------------------------------------------------------------
set "PYTHON_CMD="
set "PYTHON_ARGS="
set "PYTHON_VERSION="

echo [STEP] Looking for a usable Python 3.9+...

REM Prefer LTS-ish builds when installed (smoother than bleeding-edge 3.14)
call :pick_python py -3.12
if defined PYTHON_CMD goto :python_ready
call :pick_python py -3.11
if defined PYTHON_CMD goto :python_ready
call :pick_python py -3.13
if defined PYTHON_CMD goto :python_ready
call :pick_python py -3.10
if defined PYTHON_CMD goto :python_ready
call :pick_python py -3.9
if defined PYTHON_CMD goto :python_ready

REM Default launcher / whatever is active (may be 3.14)
call :pick_python py -3
if defined PYTHON_CMD goto :python_ready

REM Last resort: python on PATH (must not be the Store stub)
call :pick_python python
if defined PYTHON_CMD goto :python_ready

echo [ERROR] No usable Python 3.9+ was found.
echo.
echo Install Python from https://www.python.org/downloads/
echo   - Choose Python 3.11 or 3.12 for the smoothest Windows install
echo   - Enable "Add python.exe to PATH"
echo   - In Windows Settings, disable App execution aliases for
echo     "python.exe" / "python3.exe" if they point to the Microsoft Store
echo.
echo Quick check in this same window:
echo   py -3 -c "import sys; print(sys.version)"
echo.
pause
exit /b 1

:python_ready
echo [INFO] Using: %PYTHON_CMD% %PYTHON_ARGS%  ^(Python %PYTHON_VERSION%^)

REM Soft warning for very new CPython where some pins may lag
for /f "tokens=1,2 delims=." %%A in ("%PYTHON_VERSION%") do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)
if "!PY_MAJOR!"=="3" if !PY_MINOR! GEQ 15 (
    echo [WARNING] Python %PYTHON_VERSION% is very new. If dependency install fails,
    echo           install Python 3.12 from python.org and re-run install.bat.
)
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

echo [STEP] Installing dependencies from requirements.txt...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install dependencies.
    echo Prefer Python 3.11/3.12 from python.org for the smoothest Windows install.
    echo If a package needs compiling, install Microsoft C++ Build Tools:
    echo   https://visualstudio.microsoft.com/visual-cpp-build-tools/
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
"%VENV_PY%" -c "import flask, flask_socketio, simple_websocket, pymodbus, serial, paho.mqtt.client, packaging, ping3, tinytuya, curses; print('OK')"
if errorlevel 1 (
    echo [ERROR] Dependency import check failed.
    echo Prefer Python 3.11/3.12, delete the venv folder, and re-run install.bat.
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
REM Startup helpers
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
echo [TIP] Keep this folder as your install location.
echo       Do not delete the venv folder after install.
echo.
pause
endlocal
exit /b 0

REM -------------------------------------------------------------
REM Subroutine: pick_python CMD [ARGS]
REM Example: call :pick_python py -3
REM          call :pick_python python
REM Sets PYTHON_CMD / PYTHON_ARGS / PYTHON_VERSION on success.
REM -------------------------------------------------------------
:pick_python
set "_C=%~1"
set "_A=%~2"
set "_V="

if /I "%_C%"=="py" (
    where py >nul 2>&1
    if errorlevel 1 goto :eof
) else (
    where "%_C%" >nul 2>&1
    if errorlevel 1 goto :eof
)

REM Reject missing runtimes / Store stubs / Python older than 3.9
%_C% %_A% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 goto :eof

REM Read version with ONLY double-quotes inside the for /f command
REM (no single quotes, no %% formatting, no Windows paths in -c)
for /f "delims=" %%i in ('%_C% %_A% -c "import sys; print(sys.version.split()[0])" 2^>nul') do set "_V=%%i"
if not defined _V goto :eof

set "PYTHON_CMD=%_C%"
set "PYTHON_ARGS=%_A%"
set "PYTHON_VERSION=%_V%"
goto :eof
