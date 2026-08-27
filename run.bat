@echo off
setlocal enabledelayedexpansion

title Nocturne Management Center

echo =======================================================
echo   NOCTURNE - Autonomous Local Agent Management Center
echo   Agent: Auri ^| Hardware: AMD Radeon RX 9070 XT
echo =======================================================
echo.

cd /d "%~dp0"

:: Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating Python virtual environment in .venv...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment. Ensure Python 3.10+ is installed.
        pause
        exit /b 1
    )
    echo [INFO] Installing required dependencies...
    .venv\Scripts\pip.exe install -r requirements.txt
)

:: Run the Native Desktop Application
echo [INFO] Launching Nocturne...
.venv\Scripts\python.exe app.py %*

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Nocturne encountered an unexpected error.
    pause
)
