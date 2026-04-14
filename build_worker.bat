@echo off
echo ============================================================
echo  Denier Submittal Worker - Build Script
echo ============================================================
echo.
echo This builds DenierWorker.exe from worker.py.
echo Run this whenever you update worker.py, then share the
echo new DenierWorker.exe with coworkers via the Teams folder.
echo.

:: Make sure we are in the script's directory
cd /d "%~dp0"

:: Install/upgrade PyInstaller
echo [1/3] Installing PyInstaller...
pip install pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo ERROR: pip failed. Make sure Python is installed and in PATH.
    pause & exit /b 1
)

:: Build the exe
echo [2/3] Building DenierWorker.exe (this takes ~60 seconds)...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "DenierWorker" ^
    --add-data "version.json;." ^
    worker.py

if errorlevel 1 (
    echo ERROR: Build failed. Check the output above.
    pause & exit /b 1
)

:: Move exe to project root for easy access
echo [3/3] Moving exe to project root...
copy /Y "dist\DenierWorker.exe" "DenierWorker.exe"

echo.
echo ============================================================
echo  BUILD COMPLETE
echo ============================================================
echo.
echo  DenierWorker.exe is ready in this folder.
echo.
echo  Next steps:
echo    1. Upload DenierWorker.exe to the Teams shared folder
echo    2. Tell coworkers to download and double-click it once
echo    3. It installs itself silently - they never touch it again
echo.
pause
