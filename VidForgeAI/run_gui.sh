#!/usr/bin/env bash
# VidForge AI - open the Studio (macOS/Linux)
cd "$(dirname "$0")"
python3 -c "import requests, edge_tts, PIL, numpy" 2>/dev/null || {
  echo "First run - installing dependencies..."
  python3 -m pip install -r requirements.txt playwright
  python3 -m playwright install chromium
}
python3 vidforge.py gui
