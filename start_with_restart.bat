@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 (
    echo [ERROR] Could not open the install folder: %~dp0
    pause
    exit /b 1
)
set "ROOT=%CD%"
set "PY=%ROOT%\venv\Scripts\python.exe"
set "CONFIG=%ROOT%\config.ini"

if not exist "%PY%" (
    echo [ERROR] Virtual environment missing. Run install.bat first.
    echo         Expected: %PY%
    pause
    popd
    exit /b 1
)
if not exist "%CONFIG%" (
    if exist "%ROOT%\config.ini.example" (
        echo [INFO] config.ini not found. Creating it from config.ini.example.
        copy /y "%ROOT%\config.ini.example" "%CONFIG%" >nul
    ) else (
        echo [ERROR] config.ini is missing from %ROOT%
        pause
        popd
        exit /b 1
    )
)
"%PY%" -c "import flask_socketio, simple_websocket, pymodbus" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Dependencies incomplete. Run install.bat first.
    pause
    popd
    exit /b 1
)

REM Exit codes from main.py:
REM   0  clean stop (Ctrl+C) - do not loop
REM   2  another window already holds the lock
REM   3  asked to restart (update or watchdog) - loop
REM   *  crash - loop

:loop
echo ========================================
echo Starting Solar Monitoring...
echo Folder: %ROOT%
echo Config: %CONFIG%
echo Web dashboard: http://localhost:8081
echo Press Ctrl+C to stop auto-restart.
echo ========================================
"%PY%" "%ROOT%\main.py"
set "EXITCODE=%ERRORLEVEL%"
if "%EXITCODE%"=="0" (
    echo.
    echo Solar Monitoring stopped.
    popd
    exit /b 0
)
if "%EXITCODE%"=="2" (
    echo.
    echo [ERROR] Solar Monitoring is already running.
    echo         This window did not load %CONFIG%.
    echo         Close the other window, then run this script again.
    pause
    popd
    exit /b 2
)
echo.
echo Script exited with errorlevel %EXITCODE%. Restarting in 20 seconds...
timeout /t 20 /nobreak >nul
goto loop
