@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment missing. Run install.bat first.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" -c "import flask_socketio, simple_websocket" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Dependencies are incomplete ^(Flask-SocketIO missing^).
    echo Run install.bat successfully before the setup wizard.
    pause
    exit /b 1
)
echo Running first-run / reconfigure setup wizard...
"venv\Scripts\python.exe" main.py --setup
set "EXITCODE=%ERRORLEVEL%"
echo.
echo Setup wizard finished with code %EXITCODE%.
pause
exit /b %EXITCODE%
