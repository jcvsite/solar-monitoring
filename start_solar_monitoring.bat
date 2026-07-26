@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment missing. Run install.bat first.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" -c "import eventlet" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Dependencies incomplete. Run install.bat successfully first.
    pause
    exit /b 1
)
echo Starting Solar Monitoring...
echo Web dashboard: http://localhost:8081
echo.
"venv\Scripts\python.exe" main.py
set "EXITCODE=%ERRORLEVEL%"
echo.
echo Solar Monitoring exited with code %EXITCODE%.
pause
exit /b %EXITCODE%
