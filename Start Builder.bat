@echo off
color 0A
echo ===================================================
echo      STARTING DENIER SUBMITTAL BUILDER AI...
echo ===================================================
echo.

:: Activate the virtual environment and start the Flask server
start /B "" ".\.venv\Scripts\python.exe" app.py

:: Wait 3 seconds to let the server boot up
timeout /t 3 /nobreak > NUL

:: Automatically open the user's default web browser to the dashboard
start http://127.0.0.1:5000

echo.
echo ✅ Dashboard opened in your web browser!
echo ⚠️ KEEP THIS BLACK WINDOW OPEN while you are working.
echo 🛑 To shut down the tool, just close this window.
echo.
pause
