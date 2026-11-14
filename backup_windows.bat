@echo off
REM ============================================================
REM  Backup: saves your projects and this version of the app into ONE zip file.
REM  Double-click it any time (before an update it runs automatically).
REM  Where:  the "backups" folder inside this app folder (e.g. D:\DTC-Studio\backups),
REM          or another folder you give:  backup_windows.bat E:\MyBackups
REM  Not included (large, can be downloaded again): .venv, .venv-clone, .venv-image, models
REM ============================================================
setlocal
cd /d "%~dp0"
set "VER=unknown"
if exist VERSION set /p VER=<VERSION
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set "STAMP=%%i"
set "DEST=%~dp0backups"
if not "%~1"=="" if /i not "%~1"=="nopause" set "DEST=%~1"
if not exist "%DEST%" mkdir "%DEST%"
set "ZIP=%DEST%\DTC-Studio-backup_v%VER%_%STAMP%.zip"

echo.
echo  Backing up version %VER% ...
echo  to %ZIP%
powershell -NoProfile -Command "$items = Get-ChildItem -Force -LiteralPath '.' | Where-Object { $_.Name -notin @('.venv','.venv-clone','.venv-image','models','updates','backups','.git') }; Compress-Archive -Path $items.FullName -DestinationPath '%ZIP%' -CompressionLevel Optimal -Force"
if errorlevel 1 goto fail
echo.
echo  Backup done.
echo  To restore: unzip it, then copy the "projects" folder back into the app folder.
if /i not "%~1"=="nopause" pause
exit /b 0

:fail
echo.
echo  Backup FAILED - is the disk full, or is a project file open in another program?
if /i not "%~1"=="nopause" pause
exit /b 1
