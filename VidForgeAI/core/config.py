"""VidForge AI - Central configuration & project paths."""
import json
import os
import sys

APP_NAME = "VidForge AI"
APP_TAGLINE = "AI Director · Edit-ready video factory"
VERSION = "2.2.2"


def _appdata() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "VidForgeAI")


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = _appdata()
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
MEDIA_CACHE = os.path.join(CACHE_DIR, "media")
LOG_FILE = os.path.join(DATA_DIR, "vidforge.log")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

for d in (DATA_DIR, PROJECTS_DIR, CACHE_DIR, MEDIA_CACHE):
    os.makedirs(d, exist_ok=True)

DEFAULTS = {
    # --- stock / royalty-free APIs (add your own keys for higher limits;
    #     Pexels/Pixabay also work keyless at low rate via public endpoints) ---
    "pexels_api_key": "",
    "pixabay_api_key": "",
    "unsplash_access_key": "",
    "coverr_api_key": "",       # reserved
    "mixkit_enabled": False,    # scraping provider – opt-in from Settings (slower, no key)
    # --- network behaviour (v2.1 hardening: no more hangs / stalled pipelines) ---
    "http_timeout_s": 12,       # per-request read timeout for search APIs
    "asset_max_mb": 80,         # cap b-roll downloads so a 4K clip can't stall a render
    "asset_dl_timeout_s": 90,   # wall-clock deadline per asset download
    "provider_budget_s": 25,    # max time search_all may spend sourcing one scene
    "enabled_providers": None,  # None = all; or list e.g. ["pexels","archive.org","wikimedia"]
    # --- LLM (your agent brain) ---
    "llm_provider": "openai",   # openai | anthropic | ollama | local
    "openai_api_key": "",
    "openai_model": "gpt-4o-mini",
    "anthropic_api_key": "",
    "anthropic_model": "claude-3-5-sonnet-latest",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3.1",
    "ollama_timeout_s": 300,
    "openai_base_url": "",      # optional: LM Studio / Groq / vLLM (OpenAI-compatible)
    "llm_timeout_s": 120,
    "browser_fallback_enabled": False,   # opt-in: real-footage web capture (needs playwright browser)
    # --- TTS ---
    "tts_engine": "edge",       # edge | pyttsx3 (local/offline) | espeak
    "tts_voice": "en-US-AriaNeural",
    "tts_rate": "+8%",
    "tts_pitch": "+0Hz",
    "pyttsx3_voice": "",
    # --- rendering ---
    "ffmpeg_path": "ffmpeg",
    "ffprobe_path": "ffprobe",
    "chrome_path": "",          # empty = auto-detect (Playwright/Edge/Chrome)
    "default_fps": 30,
    "default_crf": 19,
    "ui_theme": "midnight",
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    # env-var overrides are handy for MCP / headless usage
    for k in ("pexels_api_key", "pixabay_api_key", "unsplash_access_key",
              "openai_api_key", "anthropic_api_key", "tts_voice", "tts_engine"):
        env = os.environ.get("VIDFORGE_" + k.upper())
        if env:
            cfg[k] = env
    # --- migrate stale configs: strip slow scraping providers from the
    #     default enabled list unless the user explicitly re-enabled them ---
    ep = cfg.get("enabled_providers")
    if isinstance(ep, list):
        cleaned = [p for p in ep if p in PROVIDER_NAMES] or None
        if cleaned != ep:
            cfg["enabled_providers"] = cleaned
    _migrate(cfg)
    return cfg


PROVIDER_NAMES = ["pexels", "pixabay", "unsplash", "coverr", "mixkit",
                  "archive.org", "wikimedia", "nasa"]


def _migrate(cfg: dict):
    """One-time fixes for older config.json files (v2.1 hardening).

    Old default configs had mixkit scraping + browser fallback ON, which could
    stall the pipeline on machines without those sites reachable. New installs
    ship them OFF; users can re-enable from Settings / MCP set_config.
    """
    changed = False
    if cfg.get("mixkit_enabled") is True and "enabled_providers" not in cfg:
        cfg["mixkit_enabled"] = False      # scraping provider – opt-in now
        changed = True
    if cfg.get("browser_fallback_enabled") is None:
        cfg["browser_fallback_enabled"] = False
        changed = True
    if not isinstance(cfg.get("http_timeout_s"), int) or cfg.get("http_timeout_s", 999) > 30:
        cfg["http_timeout_s"] = 12
        changed = True
    if cfg.get("asset_max_mb", 9999) > 500:
        cfg["asset_max_mb"] = 80
        changed = True
    if cfg.get("provider_budget_s", 9999) > 120:
        cfg["provider_budget_s"] = 25
        changed = True
    if changed:
        save_config(cfg)


def save_config(cfg: dict) -> None:
    clean = {k: v for k, v in cfg.items()}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)


CFG = load_config()
