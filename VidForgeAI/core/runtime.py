"""VidForge AI - Runtime helpers for PyInstaller-frozen (.exe) builds.

Why this exists
---------------
When VidForgeAI.exe is double-clicked, Windows extracts the bundle to a temp
dir and the GUI thread starts. Three things used to make it look "stuck on
loading" forever:

  1. Any heavy import (playwright / PIL fonts / numpy) at startup can stall
     or crash silently inside a --windowed exe (no console to show the error).
  2. The bundled ffmpeg binary shipped by imageio-ffmpeg was named plain
     "ffmpeg.exe", which collides with a real system ffmpeg sitting earlier
     on PATH -> renders fail with confusing errors.
  3. No crash log existed, so nothing could be diagnosed remotely.

These helpers are dependency-free and safe to call from anywhere.
"""
from __future__ import annotations

import os
import sys


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle (VidForgeAI.exe)."""
    return bool(getattr(sys, "frozen", False))


def meipass_root() -> str:
    """Base dir of the extracted bundle (data files live under here)."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundled_ffmpeg_name() -> str:
    """Unique name we give the pip-bundled ffmpeg inside the .exe so it can
    never collide with a system-installed ffmpeg.exe on PATH."""
    return "vidforge_ffmpeg.exe" if sys.platform.startswith("win") else "vidforge_ffmpeg"


def playwright_available() -> bool:
    """True only when BOTH the playwright package AND a usable browser binary
    exist. Inside the .exe we deliberately exclude playwright from the bundle
    (it drags in 30+ MB and its driver can hang startup on extraction), so the
    research-browser feature degrades gracefully to stock APIs instead."""
    try:
        import importlib.util
        if importlib.util.find_spec("playwright") is None:
            return False
        import os
        # playwright's default browser install location
        base = os.environ.get("LOCALAPPDATA", "") or os.path.expanduser("~/.cache/ms-playwright")
        if os.name == "nt":
            base = os.path.join(base, "ms-playwright")
        return any(d.startswith("chromium") for d in os.listdir(base)) if os.path.isdir(base) else False
    except Exception:
        return False


def locate_bundled_ffmpeg() -> str | None:
    """Find the vidforge-named ffmpeg that build_exe.bat ships inside the exe."""
    name = bundled_ffmpeg_name()
    candidates = []
    root = meipass_root()
    candidates += [os.path.join(root, name), os.path.join(root, "_internal", name)]
    exe_dir = os.path.dirname(sys.executable) if is_frozen() else root
    candidates += [os.path.join(exe_dir, name), os.path.join(exe_dir, "_internal", name)]
    for c in candidates:
        if c and os.path.isfile(c):
            try:
                os.chmod(c, 0o755)
            except OSError:
                pass
            return c
    return None
