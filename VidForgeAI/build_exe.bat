@echo off
REM ============================================================
REM  Build VidForgeAI.exe (single-file, windowed app)
REM  Auto-installs PyInstaller if missing. Works on any Python.
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM --- find a working python launcher -------------------------
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY ( py -3 --version >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python3 --version >nul 2>&1 && set "PY=python3" )
if not defined PY (
  echo ERROR: Python not found on PATH. Install Python 3.10+ from python.org
  echo (tick "Add python.exe to PATH" during installer) and run this again.
  pause & exit /b 1
)
echo Using interpreter: %PY%
%PY% --version

REM --- make sure pip exists -----------------------------------
%PY% -m pip --version >nul 2>&1 || (
  echo Installing pip...
  %PY% -m ensurepip --upgrade
)

REM --- install PyInstaller if missing -------------------------
%PY% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo Installing PyInstaller ...
  %PY% -m pip install --upgrade pip
  %PY% -m pip install pyinstaller
)
%PY% -m PyInstaller --version >nul 2>&1 || (
  echo ERROR: PyInstaller still not available.
  echo Try manually:  %PY% -m pip install pyinstaller
  pause & exit /b 1
)

REM --- build --------------------------------------------------
echo Building VidForgeAI.exe ...
%PY% -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name VidForgeAI ^
  --collect-all edge_tts ^
  --collect-all pyttsx3 ^
  --collect-all playwright ^
  --collect-data imageio_ffmpeg ^
  --hidden-import PIL._tkinter_finder ^
  --hidden-import requests ^
  --exclude-module matplotlib ^
  --exclude-module scipy ^
  vidforge.py

if exist dist\VidForgeAI.exe (
  echo.
  echo ============ SUCCESS: dist\VidForgeAI.exe ============
  echo Double-click it to open the Studio.
) else (
  echo BUILD FAILED - scroll up for errors.
  echo Common fixes:
  echo   1^) %PY% -m pip install --upgrade pyinstaller
  echo   2^) Run setup_windows.bat first to install all dependencies
  echo   3^) If Python is 3.14+, use Python 3.11/3.12 (some libs lag behind)
)
pause
