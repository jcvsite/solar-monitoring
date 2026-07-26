@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment missing. Run install.bat first.
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
