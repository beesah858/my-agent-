<div align="center">

# 🎬 VidForge AI

**The Local AI Video Studio — Idea → Ready-to-Publish Video**

A powerful, open-source desktop studio that turns a single prompt into a fully edited,
YouTube-ready video: researched script, AI narration with **word-level audio→video sync**,
royalty-free footage & images, CapCut-style animated captions, Remotion + HyperFrame
motion graphics, music ducking, LUFS normalization and one-click render.

*Runs 100% locally. No subscriptions. Full control to you — or to your AI agent via MCP.*

[![Version](https://img.shields.io/badge/version-2.2.1-blue)]()
[![Python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.12-green)]()
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)
[![Remotion](https://img.shields.io/badge/motion%20graphics-Remotion%20%2B%20HyperFrame-red)]()

</div>

---

## ✨ Features

### 🧠 AI Director (magiclight.ai style)
- One prompt → research → expert script (hook / body / CTA scenes) → narration → edit → render
- **Auto audio-video sync**: every scene's footage is frame-locked to its voice-over duration — what is spoken is what is shown
- Short-form (9:16 vertical w/ progress bar) and long-form (16:9) pipelines
- Bring your own LLM: OpenAI, Anthropic, Groq, or fully-local **Ollama** — or use the built-in offline director with zero keys

### 🔊 Voice-Over Engine
- **Edge-TTS** (400+ neural voices) with fixed `WordBoundary` timestamps for karaoke-accurate captions
- Fully **offline fallbacks**: pyttsx3 (Windows SAPI5 / macOS / espeak) — no internet needed
- Voice rotation, retry logic, per-word timing export

### 💬 Captions — CapCut Style
- **384 animated presets**: Pop Bounce, Karaoke Sweep, Neon Glow, Zoom Punch, Shake, Wave, Typewriter, Meme, Lower-Third… × 12 palettes × fonts × positions
- Per-word ASS animation driven by real speech timestamps
- "Create New Caption" designer tab + live PNG previews + `.srt` export

### 🌐 Royalty-Free Media (8 providers)
Pexels · Pixabay · Unsplash · Coverr · Mixkit · Archive.org · DuckDuckGo Images · local cache
— with license tracking. API keys go in Settings; keyless providers work out of the box.

### 🧭 Built-in Research Browser
Playwright-powered headless Chromium: search real events, sniff `og:video` / page media,
and download authentic footage & images for your topic — automatically credited & cached.

### 📊 Motion Graphics Lab — Remotion + HyperFrame
- **11 Remotion compositions**: LowerThird, StatCounter, KineticTitle, BarChart, QuoteCard, SubscribeBumper… rendered as transparent alpha overlays (ProRes/WebM) or opaque clips
- **HyperFrame data dashboards**: 6 layouts × 7 tile types (stat, bar, line, pie, text, image, spacer), auto-scene-card generator, news tickers
- Classic PIL renderer included as zero-dependency fallback

### ✂️ Clipper & Timeline Editor
- Long → short clipping with **9:16 auto-reframe** for Shorts/Reels
- Smart highlight finder (loudness-based) from long videos
- Editable timeline: reorder scenes, trim, speed ramps, transitions (xfade), picture-in-picture, re-render any project

### 🤖 MCP Server — Give Your AI Agent Full Control
JSON-RPC stdio server exposing **23 tools** (generate_video, write_script, search_media,
download, browser_open, motion graphics, clip, render, caption designer, set_config…).
Plug into Claude Desktop, Cursor or any MCP client — an LLM can now direct your whole studio.

### ⚙️ Pro Polish
-14 LUFS YouTube loudness normalization · chapter markers · sidechain music ducking ·
Ken-Burns on stills · watermark slot · progress bar for shorts · `edit_decision.json`
export for external editors · bundled FFmpeg fallback (imageio-ffmpeg).

---

## 🚀 Quick Start

### Windows — easiest (double-click)
1. Install **Python 3.10 – 3.12** from python.org (tick *"Add python.exe to PATH"*)
   ⚠️ Avoid Python 3.13/3.14 — PyInstaller & several libraries lag behind on brand-new Python versions. If you already have 3.14, install 3.11 side-by-side and run the scripts with `py -3.11`.
2. Optional but recommended: install **Node.js LTS** from nodejs.org (for Remotion/HyperFrame motion graphics) and **FFmpeg** (`winget install Gyan.FFmpeg` — or the app auto-uses its bundled fallback)
3. Open the `VidForgeAI` folder → double-click **`run_gui.bat`**
   *(first run automatically executes setup: pip deps + Playwright Chromium + npm install, then opens the Studio)*

Or manually:
```bat
setup_windows.bat     :: installs Python deps + Playwright Chromium + Node/Remotion deps
run_gui.bat           :: opens the Studio window
python vidforge.py generate "5 deep ocean secrets" --short
```

### macOS / Linux — double-click / one command
```bash
cd VidForgeAI && ./run_gui.sh    # auto-installs deps on first run, then opens Studio
```
(Requires Python 3.10+; on macOS Tk is built-in, on Linux: `sudo apt install python3-tk`)

### Any OS (manual)
```bash
cd VidForgeAI
pip install -r requirements.txt
playwright install chromium
# optional but recommended for Remotion/HyperFrame motion graphics:
cd remotion && npm install && cd ..
python vidforge.py generate "5 deep ocean secrets nobody expected" --short
open projects/<your-project>/final.mp4
```

### Build the .exe
```bat
build_exe.bat         :: PyInstaller single-file → dist\VidForgeAI.exe
```

## 📟 CLI Examples
```bash
python vidforge.py gui                                   # professional dark studio UI (8 tabs)
python vidforge.py generate "<idea>" [--short] [--long]  # full AI pipeline
python vidforge.py tts "Hello world" -v ar-AreefNeural   # voice-over + word timings
python vidforge.py captions proj/narration.json          # animated subtitle burn-in
python vidforge.py clip input.mp4 --vertical --highlight # smart shorts clipping
python vidforge.py hyperframe stats.json                 # data dashboard clip
python vidforge.py mcp                                   # run the MCP server (stdio)
```

## 🕹 Using the MCP Agent Server
Add to Claude Desktop `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "vidforge": {
      "command": "python",
      "args": ["C:/path/to/VidForgeAI/mcp/server.py"]
    }
  }
}
```
Then tell your agent: *"Make me a 60-second short about black holes with neon captions."*

## 🗂 Project Layout
```
VidForgeAI/
├── vidforge.py              # CLI entry point
├── core/
│   ├── director.py          # AI pipeline: script → sync → render
│   ├── tts_engine.py        # Edge-TTS + offline fallbacks (WordBoundary fix)
│   ├── captions.py          # 384 animated caption presets + ASS/SRT
│   ├── media_search.py      # 8 royalty-free providers + cache + licenses
│   ├── browser.py           # built-in Playwright research browser
│   ├── motion_graphics.py   # PIL fallback renderer
│   ├── remotion_bridge.py   # Python ↔ Remotion render bridge
│   ├── hyperframe.py        # HyperFrame dashboard/ticker engine
│   ├── render_engine.py     # FFmpeg assembly, xfade, ducking, LUFS
│   └── config.py            # settings, keys, profiles
├── ui/app.py                # Tkinter dark studio UI (8 tabs)
├── mcp/server.py            # MCP JSON-RPC server (23 tools)
├── remotion/src/            # Remotion comps: kit.tsx + hyperframe.tsx
├── setup_windows.bat        # one-shot dependency installer
├── build_exe.bat            # PyInstaller .exe builder
└── requirements.txt
```

## ⚖️ Licenses & Ethics
All media providers are used under their royalty-free terms; downloaded assets keep a
license manifest (`data/licenses.json`). This project does **not** scrape or clone any
paid service — it is an independent local studio inspired by the AI-video genre.

## 🛣 Roadmap
- [ ] Urdu/Hindi RTL caption fonts
- [ ] AI thumbnail generator
- [ ] A/B multi-export presets
- [ ] Multi-track timeline with drag-drop in UI

## 📄 License
MIT — see [LICENSE](LICENSE).
