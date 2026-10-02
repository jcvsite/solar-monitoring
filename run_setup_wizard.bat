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
    echo [ERROR] Dependencies are incomplete ^(Flask-SocketIO missing^).
    echo Run install.bat successfully before the setup wizard.
    pause
    popd
    exit /b 1
)
echo Running setup wizard...
echo Config: %CONFIG%
echo.
"%PY%" "%ROOT%\main.py" --setup
set "EXITCODE=%ERRORLEVEL%"
echo.
echo Setup wizard finished with code %EXITCODE%.
pause
popd
exit /b %EXITCODE%
