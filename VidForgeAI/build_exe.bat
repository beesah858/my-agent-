@echo off
REM ============================================================
REM  Build VidForgeAI.exe (single-file, windowed app)
REM  Auto-installs PyInstaller if missing. Works on any Python.
REM  v2.2.2 fixes:
REM   - exe now OPENS the Studio when double-clicked (no args needed)
REM   - bundled ffmpeg ships as vidforge_ffmpeg.exe (no PATH collisions)
REM   - startup errors are logged + shown in a dialog (no silent hangs)
REM   - side-by-side VidForgeAI_data\remotion kept for motion graphics
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM --- find a working python launcher -------------------------
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY ( py -3.12 --version >nul 2>&1 && set "PY=py -3.12" )
if not defined PY ( py -3.11 --version >nul 2>&1 && set "PY=py -3.11" )
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

REM --- stage the uniquely-named bundled ffmpeg ----------------
echo Staging bundled ffmpeg as vidforge_ffmpeg.exe ...
%PY% -c "import imageio_ffmpeg,shutil,os;shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(),os.path.join('dist_assets','vidforge_ffmpeg.exe')) if os.path.isdir('dist_assets') else None" 2>nul
if not exist dist_assets mkdir dist_assets
%PY% -c "import imageio_ffmpeg,shutil;shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(),r'dist_assets\vidforge_ffmpeg.exe')" 2>nul
if not exist dist_assets\vidforge_ffmpeg.exe (
  echo WARNING: imageio-ffmpeg not found - run setup_windows.bat first.
  echo          Building without bundled ffmpeg ^(system ffmpeg will be used^).
)

REM --- build --------------------------------------------------
echo Building VidForgeAI.exe ...
%PY% -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name VidForgeAI ^
  --add-data "dist_assets/vidforge_ffmpeg.exe;." ^
  --collect-all edge_tts ^
  --collect-all pyttsx3 ^
  --hidden-import PIL._tkinter_finder ^
  --hidden-import requests ^
  --exclude-module matplotlib ^
  --exclude-module scipy ^
  --exclude-module playwright ^
  vidforge.py

if exist dist\VidForgeAI.exe (
  echo.
  echo ============ SUCCESS: dist\VidForgeAI.exe ============
  echo Double-click it - the Studio window opens directly.
  echo.
  echo MOTION GRAPHICS ^(Remotion/HyperFrame^) need Node.js. If node is installed,
  echo this folder already has remotion\src - copy it next to the exe once:
  echo   xcopy /E /I remotion dist\VidForgeAI_data\remotion
  echo then run inside that folder:  npm install
  echo ^(Without it, VidForge falls back to built-in PIL motion cards - fully OK.^)
) else (
  echo BUILD FAILED - scroll up for errors.
  echo Common fixes:
  echo   1^) %PY% -m pip install --upgrade pyinstaller
  echo   2^) Run setup_windows.bat first to install all dependencies
  echo   3^) If Python is 3.14+, use Python 3.11/3.12 (some libs lag behind)
)

REM --- smoke test: exe must at least print its CLI help -------
if exist dist\VidForgeAI.exe (
  echo Smoke-testing exe ^(help^)...
  dist\VidForgeAI.exe --help >nul 2>&1 && echo   OK: exe launches and responds.
)
pause
