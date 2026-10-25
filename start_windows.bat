@echo off
REM Double-click to start. Keep this window open while you use the app.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Please run setup_windows.bat first.
  pause
  exit /b 1
)
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000"
.venv\Scripts\python.exe -m app.main
pause
