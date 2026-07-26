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
echo [INFO] Supported: Python 3.9+  ^(3.14 OK with current requirements^)
echo.

REM -------------------------------------------------------------
REM Locate a real Python 3.9+ interpreter
REM Prefer py launcher versions with good wheel support, then python.
REM Skip the Windows Store "python" stub that is not a real install.
REM -------------------------------------------------------------
set "PYTHON_CMD="
set "PYTHON_ARGS="

call :try_python py "-3.12"
if defined PYTHON_CMD goto :python_ready
call :try_python py "-3.11"
if defined PYTHON_CMD goto :python_ready
call :try_python py "-3.13"
if defined PYTHON_CMD goto :python_ready
call :try_python py "-3.10"
if defined PYTHON_CMD goto :python_ready
call :try_python py "-3.9"
if defined PYTHON_CMD goto :python_ready
call :try_python py "-3"
if defined PYTHON_CMD goto :python_ready
call :try_python python ""
if defined PYTHON_CMD goto :python_ready

echo [ERROR] No usable Python 3.9+ was found.
echo.
echo Install Python from https://www.python.org/downloads/
echo   - Choose Python 3.11 or 3.12 for the smoothest Windows install
echo   - Enable "Add python.exe to PATH"
echo   - In Windows Settings, disable App execution aliases for
echo     "python.exe" / "python3.exe" if they point to the Microsoft Store
echo.
pause
exit /b 1

:python_ready
echo [STEP] Checking Python version...
set "PYTHON_VERSION="
REM Avoid single quotes inside for /f (breaks on f-strings). Write version to a temp file instead.
set "PYVER_FILE=%TEMP%\solar_mon_pyver_%RANDOM%.txt"
%PYTHON_CMD% %PYTHON_ARGS% -c "import sys; v=sys.version_info; open(r'%PYVER_FILE%','w',encoding='utf-8').write('%d.%d.%d' % (v.major,v.minor,v.micro))" >nul 2>&1
if exist "%PYVER_FILE%" (
    set /p PYTHON_VERSION=<"%PYVER_FILE%"
    del /q "%PYVER_FILE%" >nul 2>&1
)
if not defined PYTHON_VERSION (
    echo [ERROR] Could not read Python version from: %PYTHON_CMD% %PYTHON_ARGS%
    echo Tip: install Python 3.12 from https://www.python.org/downloads/
    echo      and disable Microsoft Store app aliases for python.exe
    pause
    exit /b 1
)

%PYTHON_CMD% %PYTHON_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python %PYTHON_VERSION% found, but Python 3.9 or newer is required.
    pause
    exit /b 1
)

echo [INFO] Using: %PYTHON_CMD% %PYTHON_ARGS%  ^(Python %PYTHON_VERSION%^)

REM Soft warning for very new CPython where some pins may lag
%PYTHON_CMD% %PYTHON_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info < (3, 15) else 1)" >nul 2>&1
if errorlevel 1 (
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

REM Install greenlet from a binary wheel first (avoids needing MSVC on Windows)
echo [STEP] Installing greenlet ^(binary wheel preferred^)...
"%VENV_PY%" -m pip install --only-binary=:all: "greenlet>=3.1.0,<3.4"
if errorlevel 1 (
    echo [WARNING] No binary greenlet wheel for this Python. Trying normal install...
    "%VENV_PY%" -m pip install "greenlet>=3.1.0,<3.4"
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not install greenlet.
        echo Python %PYTHON_VERSION% may not have a prebuilt wheel yet.
        echo Fix options:
        echo   1^) Install Python 3.12 from https://www.python.org/downloads/ and re-run
        echo   2^) Or install "Microsoft C++ Build Tools" and re-run
        echo.
        pause
        exit /b 1
    )
)

echo [STEP] Installing remaining dependencies from requirements.txt...
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
"%VENV_PY%" -c "import eventlet, flask, flask_socketio, pymodbus, serial, paho.mqtt.client, packaging, ping3, tinytuya, curses, greenlet; print('OK')"
if errorlevel 1 (
    echo [ERROR] Dependency import check failed.
    echo Re-run install.bat after fixing the errors above.
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
REM Subroutine: try_python CMD ARGS
REM Sets PYTHON_CMD / PYTHON_ARGS if the interpreter is real and >= 3.9
REM -------------------------------------------------------------
:try_python
set "_CAND_CMD=%~1"
set "_CAND_ARGS=%~2"
if /I "%_CAND_CMD%"=="py" (
    where py >nul 2>&1
    if errorlevel 1 goto :eof
) else (
    where %_CAND_CMD% >nul 2>&1
    if errorlevel 1 goto :eof
)

REM Must actually run Python code (rejects Microsoft Store stub / missing -3.xx)
%_CAND_CMD% %_CAND_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    set "_CAND_CMD="
    set "_CAND_ARGS="
    goto :eof
)

REM Confirm this exact candidate can report a version (same method as main path)
set "_CAND_VER_FILE=%TEMP%\solar_mon_cand_%RANDOM%.txt"
%_CAND_CMD% %_CAND_ARGS% -c "import sys; v=sys.version_info; open(r'%_CAND_VER_FILE%','w',encoding='utf-8').write('%d.%d.%d' % (v.major,v.minor,v.micro))" >nul 2>&1
if not exist "%_CAND_VER_FILE%" (
    set "_CAND_CMD="
    set "_CAND_ARGS="
    goto :eof
)
del /q "%_CAND_VER_FILE%" >nul 2>&1

set "PYTHON_CMD=%_CAND_CMD%"
set "PYTHON_ARGS=%_CAND_ARGS%"
goto :eof
