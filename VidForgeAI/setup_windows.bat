@echo off
REM ============================================================
REM  VidForge AI - one-click setup for Windows
REM  Installs Python deps + FFmpeg fallback + Playwright browser
REM ============================================================
cd /d "%~dp0"
echo [1/4] Checking Python...
python --version || (echo Install Python 3.10+ from python.org first ^(tick "Add python.exe to PATH"^)! & pause & exit /b 1)
python -c "import sys; sys.exit(0 if (3,10)<=sys.version_info<(3,13) else 1)" || echo   WARNING: Python version outside 3.10-3.12. Some libraries may not support it yet. If the build fails, install Python 3.11 from python.org.

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --version >nul 2>&1 || echo   ERROR: PyInstaller install failed. Run: python -m pip install pyinstaller

echo [3/5] Installing built-in research browser (Chromium)...
python -m playwright install chromium

echo [4/5] Installing Remotion motion-graphics engine (needs Node.js, optional)...
where node >nul 2>nul && (pushd remotion & call npm install --no-audit --no-fund & popd) || echo   Node.js not found - skipping Remotion/HyperFrame (PIL fallback still works).

echo [5/5] Smoke test: TTS engine...
python vidforge.py tts "Vid Forge studio is ready." -o "%TEMP%\vf_test.mp3"

echo.
echo ============ VidForge AI installed OK ============
echo   Start GUI ......... run_gui.bat   (or VidForgeAI.exe after build)
echo   CLI ............... python vidforge.py generate "your idea" --short
echo   Build .exe ........ build_exe.bat
pause
