@echo off
REM ============================================================
REM  One-time setup (needs internet once). Double-click this file.
REM  Options:  setup_windows.bat small   -> smaller/faster voice model
REM            setup_windows.bat gpu     -> use your graphics card for the voice (DirectML)
REM            setup_windows.bat piper   -> extra languages (Piper voices)
REM            setup_windows.bat clone   -> voice clone: speak in YOUR voice (about 3 GB)
REM            setup_windows.bat ai      -> local AI writer/translator (Ollama + Llama 3.2, about 2 GB)
REM                                         and captions from your recordings (Whisper, about 0.5 GB)
REM            setup_windows.bat images  -> picture creator from a prompt (about 3 GB)
REM  Options can be combined, e.g.  setup_windows.bat clone ai images
REM ============================================================
cd /d "%~dp0"
setlocal EnableDelayedExpansion
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Python is not installed. Install Python 3.11 or 3.12 from https://www.python.org/downloads/
  echo  and tick "Add python.exe to PATH" during install. Then run this file again.
  pause
  exit /b 1
)
set "MODELARGS="
set "WANTGPU="
set "WANTPIPER="
set "WANTCLONE="
set "WANTAI="
set "WANTIMAGES="
for %%a in (%*) do (
  if /i "%%a"=="small" set "MODELARGS=%MODELARGS% --small"
  if /i "%%a"=="gpu" set "WANTGPU=1"
  if /i "%%a"=="piper" set "WANTPIPER=1"
  if /i "%%a"=="clone" set "WANTCLONE=1"
  if /i "%%a"=="ai" set "WANTAI=1"
  if /i "%%a"=="images" set "WANTIMAGES=1"
)
if defined WANTPIPER set "MODELARGS=%MODELARGS% --piper"

echo [1/3] Creating private Python environment (.venv)...
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
if errorlevel 1 goto fail
set "VPY=.venv\Scripts\python.exe"
REM slow or unstable internet: wait longer and retry more often
set "PIP_DEFAULT_TIMEOUT=120"
set "PIP_RETRIES=10"

echo [2/3] Installing open-source packages...
%VPY% -m pip install --upgrade pip >nul
%VPY% -m pip install -r requirements.txt
if errorlevel 1 goto fail
if defined WANTGPU (
  %VPY% -m pip uninstall -y onnxruntime
  %VPY% -m pip install onnxruntime-directml
)
if defined WANTPIPER %VPY% -m pip install -r requirements-optional.txt

echo [3/3] Downloading offline voice models (one time)...
%VPY% scripts\download_models.py %MODELARGS%
if errorlevel 1 goto fail

if defined WANTCLONE (
  echo [4/4] Installing the voice clone in its own environment .venv-clone ...
  if not exist .venv-clone\Scripts\python.exe %PY% -m venv .venv-clone
  if errorlevel 1 goto fail
  .venv-clone\Scripts\python.exe -m pip install --upgrade pip >nul
  set "TORCHIDX=https://download.pytorch.org/whl/cpu"
  if defined WANTGPU (
    where nvidia-smi >nul 2>nul && set "TORCHIDX=https://download.pytorch.org/whl/cu124"
  )
  .venv-clone\Scripts\python.exe -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url !TORCHIDX!
  if errorlevel 1 goto fail
  .venv-clone\Scripts\python.exe -m pip install -r requirements-clone.txt
  if errorlevel 1 goto fail
  set "HF_HOME=%CD%\models\hf"
  .venv-clone\Scripts\python.exe scripts\download_clone_model.py
  if errorlevel 1 goto fail
)

if defined WANTAI (
  echo [AI] Captions from recordings: installing faster-whisper...
  %VPY% -m pip install -r requirements-ai.txt
  if errorlevel 1 goto fail
  set "HF_HOME=%CD%\models\hf"
  %VPY% scripts\download_ai_models.py
  if errorlevel 1 goto fail
  echo [AI] Local AI writer: Ollama...
  where ollama >nul 2>nul
  if errorlevel 1 (
    winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
      echo  Could not install Ollama automatically. Download it from https://ollama.com/download
      echo  install it, then run:  setup_windows.bat ai   again.
      goto fail
    )
    set "PATH=%LOCALAPPDATA%\Programs\Ollama;!PATH!"
  )
  echo [AI] Downloading the writer model llama3.2:3b - about 2 GB, one time...
  ollama pull llama3.2:3b
  if errorlevel 1 goto fail
)

if defined WANTIMAGES (
  echo [Pictures] Installing the picture creator in its own environment .venv-image ...
  if not exist .venv-image\Scripts\python.exe %PY% -m venv .venv-image
  if errorlevel 1 goto fail
  .venv-image\Scripts\python.exe -m pip install --upgrade pip >nul
  .venv-image\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  if errorlevel 1 goto fail
  .venv-image\Scripts\python.exe -m pip install -r requirements-image.txt
  if errorlevel 1 goto fail
  set "HF_HOME=%CD%\models\hf"
  .venv-image\Scripts\python.exe scripts\download_image_model.py
  if errorlevel 1 goto fail
)

echo.
echo  Setup complete. Double-click start_windows.bat to open the app.
pause
exit /b 0

:fail
echo.
echo  Setup failed - read the red text above, or send a screenshot of it.
pause
exit /b 1
