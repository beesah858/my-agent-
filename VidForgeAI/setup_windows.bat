@echo off
REM ============================================================
REM  VidForge AI - one-click setup for Windows
REM  Installs Python deps + FFmpeg fallback + Playwright browser
REM ============================================================
cd /d "%~dp0"
echo [1/4] Checking Python...
python --version || (echo Install Python 3.10+ from python.org first! & pause & exit /b 1)

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller

echo [3/4] Installing built-in research browser (Chromium)...
python -m playwright install chromium

echo [4/4] Smoke test: TTS engine...
python vidforge.py tts "Vid Forge studio is ready." -o "%TEMP%\vf_test.mp3"

echo.
echo ============ VidForge AI installed OK ============
echo   Start GUI ......... run_gui.bat   (or VidForgeAI.exe after build)
echo   CLI ............... python vidforge.py generate "your idea" --short
echo   Build .exe ........ build_exe.bat
pause
