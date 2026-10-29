@echo off
REM ============================================================
REM  VidForge AI - double-click to open the Studio (Windows)
REM  Runs from this folder; if deps missing, runs setup first.
REM ============================================================
cd /d "%~dp0"
python -c "import requests, edge_tts, PIL, numpy" 2>nul
if errorlevel 1 (
  echo First run detected - installing dependencies...
  call setup_windows.bat
)
start "" pythonw vidforge.py gui
