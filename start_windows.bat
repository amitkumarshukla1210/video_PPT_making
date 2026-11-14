@echo off
REM Double-click to start. Keep this window open while you use the app.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Please run install_once.bat first.
  pause
  exit /b 1
)
REM The app uses port 8080. Another port: set DTC_PORT=9000 before starting.
if not defined DTC_PORT set "DTC_PORT=8080"
start "" cmd /c "timeout /t 4 >nul & start http://localhost:%DTC_PORT%"
.venv\Scripts\python.exe -m app.main
pause
