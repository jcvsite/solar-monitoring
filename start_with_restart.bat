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
echo Script exited with errorlevel %EXITCODE%. Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto loop
