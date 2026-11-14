@echo off
REM ============================================================
REM  Update to the newest version. Your projects, voice models and settings are kept.
REM  1. It makes a backup first (backup_windows.bat).
REM  2. It uses a ZIP you put in the "updates" folder, or else downloads the latest release
REM     from GitHub. (If the repository is private, download the ZIP in your browser and
REM     put it in the "updates" folder, then run this again.)
REM  3. It copies the new files over the old ones and installs any new Python packages.
REM ============================================================
REM Run from a temporary copy: this file itself may be replaced by the update.
if /i not "%~1"=="--from-temp" (
  copy /y "%~f0" "%TEMP%\dtc_update.bat" >nul
  "%TEMP%\dtc_update.bat" --from-temp "%~dp0"
  exit /b
)
setlocal EnableDelayedExpansion
cd /d "%~2"
set "REPO=amitkumarshukla1210/video_PPT_making"
set "OLD=unknown"
if exist VERSION set /p OLD=<VERSION
echo.
echo  Current version: %OLD%
echo.
echo [1/4] Backup first...
call backup_windows.bat nopause
if errorlevel 1 goto fail

if not exist updates mkdir updates
set "ZIPFILE="
for %%f in (updates\*.zip) do set "ZIPFILE=%%f"
if defined ZIPFILE goto install

echo [2/4] Downloading the latest version from GitHub...
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; foreach ($u in @('https://github.com/%REPO%/releases/latest/download/DTC-Studio.zip','https://github.com/%REPO%/archive/refs/heads/main.zip')) { try { Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile 'updates\latest.zip'; exit 0 } catch { } }; exit 1"
if errorlevel 1 goto nodownload
set "ZIPFILE=updates\latest.zip"

:install
echo [3/4] Installing !ZIPFILE! ...
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $t = Join-Path $env:TEMP 'dtc-update'; if (Test-Path $t) { Remove-Item $t -Recurse -Force }; Expand-Archive -LiteralPath '!ZIPFILE!' -DestinationPath $t -Force; $src = Get-ChildItem $t -Directory | Select-Object -First 1; if (-not (Test-Path (Join-Path $src.FullName 'app\main.py'))) { throw 'This ZIP is not the Design to Cost app.' }; Copy-Item -Path (Join-Path $src.FullName '*') -Destination '.' -Recurse -Force; Remove-Item $t -Recurse -Force"
if errorlevel 1 goto fail
if not exist updates\installed mkdir updates\installed
move /y "!ZIPFILE!" updates\installed\ >nul

echo [4/4] Installing any new Python packages...
set "PIP_DEFAULT_TIMEOUT=120"
set "PIP_RETRIES=10"
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 goto fail
if exist .venv-clone\Scripts\python.exe .venv-clone\Scripts\python.exe -m pip install -q -r requirements-clone.txt
if exist .venv-image\Scripts\python.exe .venv-image\Scripts\python.exe -m pip install -q -r requirements-image.txt
.venv\Scripts\python.exe -c "import faster_whisper" >nul 2>nul && .venv\Scripts\python.exe -m pip install -q -r requirements-ai.txt

set "NEW=unknown"
if exist VERSION set /p NEW=<VERSION
echo.
echo  Updated: %OLD%  -^>  %NEW%
echo  See CHANGELOG.md for what is new. Start the app with start_windows.bat.
pause
exit /b 0

:nodownload
echo.
echo  Could not download the update - no internet, or the repository is private.
echo  Do this instead:
echo    1. In your browser open https://github.com/%REPO%
echo    2. Click Code, then Download ZIP. Or open Releases and download DTC-Studio.zip
echo    3. Put the ZIP file into:  %CD%\updates
echo    4. Run update_windows.bat again.
pause
exit /b 1

:fail
echo.
echo  Update FAILED. Nothing was lost: your backup is in the backups folder.
echo  Send a screenshot of this window for help.
pause
exit /b 1
