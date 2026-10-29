@echo off
REM ============================================================
REM  Build VidForgeAI.exe (single-file, windowed app)
REM  Requires: pyinstaller (setup_windows.bat installs it)
REM ============================================================
cd /d "%~dp0"
echo Building VidForgeAI.exe ...
python -m PyInstaller ^
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
)
pause
