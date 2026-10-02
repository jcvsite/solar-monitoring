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
"%PY%" -c "import flask_socketio, simple_websocket" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Dependencies incomplete. Run install.bat successfully first.
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
echo Starting Solar Monitoring...
echo Folder: %ROOT%
echo Config: %CONFIG%
echo Web dashboard: http://localhost:8081
echo.
"%PY%" "%ROOT%\main.py"
set "EXITCODE=%ERRORLEVEL%"
if "%EXITCODE%"=="2" (
    echo.
    echo [ERROR] Solar Monitoring is already running.
    echo         This window did not load %CONFIG%.
    echo         Close the other window, then run this script again.
)
echo.
echo Solar Monitoring exited with code %EXITCODE%.
pause
popd
exit /b %EXITCODE%
