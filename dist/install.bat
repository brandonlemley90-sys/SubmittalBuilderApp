@echo off
echo ========================================
echo DenierAI_Submittal_Builder Installer
echo Version 1.0.0
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Please run as Administrator
    pause
    exit /b
)

REM Set installation directory
set INSTALL_DIR=%PROGRAMFILES%\DenierAI_Submittal_Builder

echo Installing to %INSTALL_DIR%
echo.

REM Create installation directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM Extract files (assuming this is run from the extracted zip)
echo Copying files...
xcopy /E /Y /Q "%~dp0*" "%INSTALL_DIR%\"

REM Create shortcut
echo Creating desktop shortcut...
powershell "$WShell = New-Object -ComObject WScript.Shell; $Shortcut = $WShell.CreateShortcut('%USERPROFILE%\Desktop\DenierAI_Submittal_Builder.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\DenierAI_Submittal_Builder.exe'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Save()"

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo You can now run DenierAI_Submittal_Builder from your desktop.
echo.
pause
