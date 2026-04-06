@echo off
echo ================================================================
echo   DenierAI Submittal Builder - Quick Install
echo ================================================================
echo.
echo This will download and install the latest version automatically.
echo.
pause

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Run the bootstrap installer
python "%~dp0bootstrap_installer.py"

pause
