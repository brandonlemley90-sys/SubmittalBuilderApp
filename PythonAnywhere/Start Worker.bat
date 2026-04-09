@echo off
title Denier Worker Console
color 0A
cd /d "%~dp0"

echo.
echo  ============================================================
echo    DenierAI Local Worker  |  Submittal Builder Agent
echo    Polling: https://lemley.pythonanywhere.com
echo  ============================================================
echo.

:: Try to detect python installation
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] "python" command not found in your PATH.
    echo Trying common install paths...
    
    IF EXIST "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
        SET PY_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    ) ELSE (
        echo [!] Could not find Python. Please install Python 3.13 or 3.14.
        pause
        exit /b 1
    )
) ELSE (
    SET PY_CMD=python
)

echo Starting worker... Keep this window open.
echo.

%PY_CMD% worker.py

echo.
echo [!] Worker stopped.
pause
