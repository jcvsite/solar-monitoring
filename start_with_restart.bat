@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment missing. Run install.bat first.
    pause
    exit /b 1
)
:loop
echo ========================================
echo Starting Solar Monitoring...
echo Web dashboard: http://localhost:8081
echo Press Ctrl+C to stop auto-restart.
echo ========================================
"venv\Scripts\python.exe" main.py
echo.
echo Script exited with errorlevel %ERRORLEVEL%. Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto loop
