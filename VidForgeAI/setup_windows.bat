@echo off
REM ============================================================
REM  VidForge AI - one-click setup for Windows
REM  Installs Python deps + FFmpeg fallback + Playwright browser
REM  NOTE: run this with the SAME python you'll build/run with.
REM        If you have several Pythons, use:  py -3.12 setup_windows.bat style:
REM        open a terminal in this folder and run:  py -3.12 -m pip install -r requirements.txt
REM ============================================================
cd /d "%~dp0"
echo [1/5] Checking Python...
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY ( py -3.12 --version >nul 2>&1 && set "PY=py -3.12" )
if not defined PY ( py -3.11 --version >nul 2>&1 && set "PY=py -3.11" )
if not defined PY ( py -3 --version >nul 2>&1 && set "PY=py -3" )
if not defined PY ( echo Install Python 3.10+ from python.org first ^(tick "Add python.exe to PATH"^)! & pause & exit /b 1 )
%PY% --version
%PY% -c "import sys; sys.exit(0 if (3,10)<=sys.version_info<(3,13) else 1)" || echo   WARNING: Python version outside 3.10-3.12. Some libraries may not support it yet. Recommended: winget install Python.Python.3.12

echo [2/5] Installing dependencies...
%PY% -m pip install --upgrade pip >nul
%PY% -m pip install -r requirements.txt pyinstaller
%PY% -m PyInstaller --version >nul 2>&1 || echo   ERROR: PyInstaller install failed. Run: %PY% -m pip install pyinstaller

echo [3/5] Installing built-in research browser (Chromium)...
%PY% -m playwright install chromium || echo   Playwright browser install failed - browser research stays OFF, everything else still works.

echo [4/5] Installing Remotion motion-graphics engine (needs Node.js, optional)...
where node >nul 2>nul && (pushd remotion & call npm install --no-audit --no-fund & popd) || echo   Node.js not found - skipping Remotion/HyperFrame (PIL fallback still works).

echo [5/5] Smoke test: TTS engine...
%PY% vidforge.py tts "Vid Forge studio is ready." -o "%TEMP%\vf_test.mp3"

echo.
echo ============ VidForge AI installed OK ============
echo   Start GUI ......... run_gui.bat   (or double-click VidForgeAI.exe after build)
echo   CLI ............... %PY% vidforge.py generate "your idea" --short
echo   Build .exe ........ build_exe.bat
pause
