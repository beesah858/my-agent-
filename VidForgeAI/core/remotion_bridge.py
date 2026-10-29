"""VidForge AI — Remotion bridge (React/TypeScript motion-graphics engine).

Drives the bundled Remotion project in <ROOT>/remotion from Python:
  * render_still()   -> fast transparent PNG frame (lower-thirds, stat pop-ups…)
  * render_clip()    -> animated overlay clip (WebM VP9 alpha / ProRes4444 MOV)
  * render_scene()   -> full-frame composition driven by a data-driven item list
  * setup()          -> one-click `npm install` + headless-shell download
  * available()      -> health check used by UI / director / MCP tools

Compositions live in remotion/src/kit.tsx & hyperframe.tsx and are prop-driven:
  LowerThird, StatCounter, KineticTitle, BarChart, QuoteCard,
  SubscribeBumper, CalloutArrow, ProgressRing, MapPing, CompareSplit, ForgeScene
  + HYPERFRAME engine (hyperframe.tsx): HyperFrame (data-driven bento/statwall/
    hero/compare/chartdash layouts with animated tiles) and HyperTicker
    (news-style scrolling fact ticker). Python facade: core/hyperframe.py

If Node.js or the npm deps are missing everything degrades gracefully to the
built-in PIL generator (motion_graphics.py) — pipelines never break.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from . import config

log = logging.getLogger("vidforge.remotion")

ROOT = config.ROOT


def _remotion_dir() -> str:
    """Inside VidForgeAI.exe the temp-extracted copy of remotion/src is NOT a
    usable project (no node_modules). So when frozen, look for a real Remotion
    project next to the exe (VidForgeAI_data/remotion) — setup_windows.bat /
    build_exe.bat create it there. Unpackaged runs keep using ROOT/remotion."""
    try:
        from .runtime import is_frozen
        if is_frozen():
            exe_dir = os.path.dirname(sys.executable)
            for cand in (os.path.join(exe_dir, "VidForgeAI_data", "remotion"),
                         os.path.join(exe_dir, "remotion")):
                if os.path.isdir(os.path.join(cand, "node_modules", "remotion")):
                    return cand
            # no side-by-side project -> point at the data dir anyway so
            # available() cleanly returns False and PIL fallback kicks in
            return os.path.join(exe_dir, "VidForgeAI_data", "remotion")
    except Exception:
        pass
    return os.path.join(ROOT, "remotion")


PROJ_DIR = _remotion_dir()
ENTRY = os.path.join(PROJ_DIR, "src", "index.tsx")

COMPOSITIONS = {
    # id -> (kind, default duration s, description)
    "LowerThird": ("overlay", 3.0, "Animated name/title bar (slide + glow underline)"),
    "StatCounter": ("overlay", 3.0, "Big number count-up with spring pop"),
    "KineticTitle": ("overlay", 4.0, "Word-by-word kinetic typography"),
    "BarChart": ("overlay", 4.0, "Spring-grown animated bar chart"),
    "QuoteCard": ("full", 5.0, "Gradient quote card with author"),
    "SubscribeBumper": ("overlay", 3.0, "YouTube subscribe button + bell pop"),
    "CalloutArrow": ("overlay", 3.0, "Hand-drawn arrow callout that bobs"),
    "ProgressRing": ("overlay", 3.3, "Circular percentage progress ring"),
    "MapPing": ("full", 3.3, "Dropping map pin with ripple ping"),
    "CompareSplit": ("overlay", 3.3, "Before/after wipe divider"),
    "HyperFrame": ("full", 6.0, "HYPERFRAME: data-driven animated dashboard (statwall/bento/hero/compare/chartdash)"),
    "HyperTicker": ("overlay", 5.0, "HYPERFRAME: scrolling news-style fact ticker"),
    "ForgeScene": ("scene", 20.0, "Full timeline scene from a data-driven item list"),
}

# HyperFrame layout presets exposed to UI / MCP / director
HF_LAYOUTS = ["grid", "statwall", "bento", "hero", "compare", "chartdash"]
HF_TILE_TYPES = ["stat", "bar", "text", "big", "chip", "list", "image"]

_lock = threading.Lock()
_avail_cache: dict = {}


# ------------------------------------------------------------------ detection
def node_bin() -> str | None:
    return shutil.which("node") or shutil.which("nodejs")


def _npx_cli() -> list[str] | None:
    """Prefer the locally installed remotion CLI binary."""
    local = os.path.join(PROJ_DIR, "node_modules", ".bin", "remotion")
    if os.path.exists(local):
        return [local]
    if os.name == "nt":
        localw = os.path.join(PROJ_DIR, "node_modules", ".bin", "remotion.cmd")
        if os.path.exists(localw):
            return ["cmd", "/c", localw]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--no-install", "remotion"]
    return None


def deps_installed() -> bool:
    return os.path.isdir(os.path.join(PROJ_DIR, "node_modules", "remotion"))


def available() -> bool:
    if _avail_cache.get("v") is not None:
        return _avail_cache["v"]
    ok = bool(node_bin()) and deps_installed() and os.path.exists(ENTRY)
    with _lock:
        _avail_cache["v"] = ok
    return ok


def setup(progress=None, install_timeout_s: int = 900) -> dict:
    """npm install + warm Remotion's headless browser shell. Idempotent."""
    if not node_bin():
        raise RuntimeError("Node.js not found — install from nodejs.org (LTS) first.")
    def say(p, m):
        if progress:
            try:
                progress(p, m)
            except Exception:
                pass
    say(0.05, "Installing Remotion npm dependencies…")
    pm = shutil.which("npm")
    if not pm:
        raise RuntimeError("npm not found (comes with Node.js LTS installer).")
    r = subprocess.run([pm, "install", "--no-audit", "--no-fund"],
                       cwd=PROJ_DIR, capture_output=True, text=True,
                       timeout=install_timeout_s)
    if r.returncode != 0:
        raise RuntimeError("npm install failed:\n" + (r.stderr or r.stdout)[-1200:])
    say(0.7, "Downloading Remotion headless browser shell…")
    cli = _npx_cli()
    subprocess.run(cli + ["compositions", ENTRY], cwd=PROJ_DIR,
                   capture_output=True, text=True, timeout=600)
    with _lock:
        _avail_cache.pop("v", None)
    say(1.0, "Remotion ready ✓")
    return {"ok": available(), "project": PROJ_DIR}


# ------------------------------------------------------------------ rendering
def _run(cmd: list[str], out_path: str, timeout_s: int, what: str) -> str:
    if not available():
        raise RuntimeError("Remotion not set up — call remotion.setup() (needs Node.js).")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    env = dict(os.environ)
    env.setdefault("REMOTION_TELEMETRY_DISABLED", "1")
    proc = subprocess.run(cmd, cwd=PROJ_DIR, capture_output=True, text=True,
                          timeout=timeout_s, env=env)
    if proc.returncode != 0 or not os.path.exists(out_path):
        tail = (proc.stderr or proc.stdout or "")[-1500:]
        raise RuntimeError(f"Remotion {what} failed:\n{tail}")
    return out_path


def render_still(comp_id: str, props: dict, out_png: str, *,
                 width: int = 1920, height: int = 1080, frame: int = 45,
                 timeout_s: int = 240) -> str:
    """One high-quality frame — perfect for lower-thirds/stat pop cards."""
    cli = _npx_cli()
    cmd = cli + ["still", ENTRY, comp_id, out_png,
                 "--frame", str(frame), "--width", str(width),
                 "--height", str(height), "--props", json.dumps(props)]
    return _run(cmd, out_png, timeout_s, "still")


def render_clip(comp_id: str, props: dict, out_path: str, *,
                width: int = 1920, height: int = 1080, fps: int = 30,
                duration_in_frames: int | None = None,
                transparent: bool = True, codec: str | None = None,
                concurrency: int | None = None,
                timeout_s: int = 900) -> str:
    """Render an animated MG clip.

    transparent=True + codec='vp9' -> WebM VP9 with alpha (small overlays).
    codec='prores' -> industry ProRes4444 .mov with alpha.
    codec='h264' / out .mp4 -> opaque full-frame video.
    NOTE: Remotion CLI does not expose --crf/--pixel-format; for alpha clips we
    render a PNG frame sequence and mux lossless WebM/ProRes via FFmpeg.
    """
    # data-driven duration: inject durationInFrames into props so compositions
    # with calculateMetadata (HyperFrame/HyperTicker) size themselves exactly.
    if duration_in_frames:
        props = {**props, "durationInFrames": int(duration_in_frames)}
    cli = _npx_cli()
    want_alpha = transparent and (codec in (None, "vp9", "prores"))
    if codec == "prores":
        default_ext = ".mov"
    elif codec == "h264" or out_path.lower().endswith(".mp4"):
        default_ext, codec = ".mp4", "h264"
    else:
        default_ext, codec = ".webm", "vp9"
    if not out_path.lower().endswith((".webm", ".mov", ".mp4", ".mkv")):
        out_path += default_ext

    if want_alpha:
        # ---- fast native path: remotion renders VP9-with-alpha webm itself ----
        # (one browser launch, parallel frames — thousands of times faster than
        #  per-frame `still` calls; falls back to PNG-sequence mux if unsupported)
        tmp_webm = out_path + ".tmp.vp9.webm"
        cmd = cli + ["render", ENTRY, comp_id, tmp_webm,
                     "--codec=vp9", "--pixel-format=yuva420p",
                     "--width", str(width), "--height", str(height),
                     "--fps", str(fps), "--props", json.dumps(props)]
        if duration_in_frames:
            cmd += ["--frames", f"0-{int(duration_in_frames) - 1}"]
        try:
            _run(cmd, tmp_webm, timeout_s, "vp9-alpha render")
            exe = _ffmpeg_for_mux()
            if codec == "prores":
                conv = [exe, "-y", "-hide_banner", "-loglevel", "error", "-i", tmp_webm,
                        "-c:v", "prores_ks", "-profile:v", "4444",
                        "-pix_fmt", "yuva444p10le", out_path]
            elif out_path.lower().endswith(".mp4"):
                # opaque mp4 requested but alpha wanted -> keep webm name fix-up
                conv = [exe, "-y", "-hide_banner", "-loglevel", "error", "-i", tmp_webm,
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path]
            else:
                conv = [exe, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", tmp_webm, "-c:v", "copy", out_path]
            r = subprocess.run(conv, capture_output=True, text=True, timeout=timeout_s)
            ok = r.returncode == 0 and os.path.exists(out_path)
            if ok:
                os.remove(tmp_webm)
                return out_path
            log.warning("alpha transcode failed (%s) — using PNG-sequence path",
                        (r.stderr or "")[-200:])
        except Exception as e:
            log.warning("native vp9-alpha render unavailable (%s) — PNG-sequence fallback", e)
        finally:
            if os.path.exists(tmp_webm):
                os.remove(tmp_webm)

        # ---- frame-sequence path (true alpha, lossless) ----
        nframes = duration_in_frames or int(COMPOSITIONS.get(comp_id, ("", 3.0))[1] * fps)
        nframes = max(1, int(nframes))
        seqdir = os.path.join(os.path.dirname(os.path.abspath(out_path)),
                              "rmseq_" + os.path.basename(out_path).split(".")[0])
        shutil.rmtree(seqdir, ignore_errors=True)
        os.makedirs(seqdir, exist_ok=True)
        # one-time bundle build -> reuse for every frame (fast)
        serve_dir = os.path.join(PROJ_DIR, ".vidforge-serve")
        bundle_ok = os.path.exists(os.path.join(serve_dir, "index.html"))
        if not bundle_ok:
            rb = subprocess.run(cli[:1] + ["bundle", ENTRY, serve_dir] if cli[0].endswith("remotion")
                                else cli + ["bundle", ENTRY, serve_dir],
                                cwd=PROJ_DIR, capture_output=True, text=True, timeout=600)
            bundle_ok = rb.returncode == 0 and os.path.exists(os.path.join(serve_dir, "index.html"))
        target = serve_dir if bundle_ok else ENTRY
        still_args = (["still", target, comp_id] if bundle_ok else ["still", ENTRY, comp_id])
        for i in range(nframes):
            fp = os.path.join(seqdir, f"f_{i:05d}.png")
            cmd = cli + still_args + [fp, "--width", str(width), "--height", str(height),
                                      "--fps", str(fps), "--image-format=png",
                                      "--frame", str(i), "--props", json.dumps(props)]
            _run(cmd, fp, 240, f"still {i}")
        exe = _ffmpeg_for_mux()
        pix = "yuva444p10le" if codec == "prores" else "yuva420p"
        venc = (["-c:v", "prores_ks", "-profile:v", "4444"] if codec == "prores"
                else ["-c:v", "libvpx-vp9", "-lossless", "1"])
        mux = [exe, "-y", "-hide_banner", "-loglevel", "error",
               "-framerate", str(fps), "-start_number", "0",
               "-i", os.path.join(seqdir, "f_%05d.png")] + venc + \
              ["-pix_fmt", pix, out_path]
        r = subprocess.run(mux, capture_output=True, text=True, timeout=timeout_s)
        shutil.rmtree(seqdir, ignore_errors=True)
        if r.returncode != 0 or not os.path.exists(out_path):
            raise RuntimeError("alpha mux failed:\n" + (r.stderr or "")[-800:])
        return out_path

    # ---- opaque mp4 fast path via remotion's own encoder ----
    cmd = cli + ["render", ENTRY, comp_id, out_path,
                 "--width", str(width), "--height", str(height),
                 "--fps", str(fps), "--image-format=png",
                 "--codec=h264", "--props", json.dumps(props)]
    if duration_in_frames:
        cmd += ["--duration-in-frames", str(max(1, int(duration_in_frames)))]
    if concurrency:
        cmd += ["--concurrency", str(concurrency)]
    return _run(cmd, out_path, timeout_s, "render")


def _ffmpeg_for_mux() -> str:
    try:
        from .render_engine import ffmpeg_bin
        return ffmpeg_bin()
    except Exception:
        return "ffmpeg"


def render_scene(items: list[dict], out_mp4: str, *, width=1920, height=1080,
                 fps=30, scene_props: dict | None = None,
                 timeout_s: int = 1800) -> str:
    """Full video composed from a data-driven item list (ForgeScene comp).

    items: [{"type":"LowerThird","dur_s":3,"props":{...}}, ...]
    """
    total_frames = sum(max(1, round(it.get("dur_s", 3) * fps)) for it in items) or 90
    props = {"items": items, **(scene_props or {})}
    cli = _npx_cli()
    cmd = cli + ["render", ENTRY, "ForgeScene", out_mp4,
                 "--width", str(width), "--height", str(height),
                 "--fps", str(fps), "--codec=h264", "--crf", "18",
                 "--duration-in-frames", str(total_frames),
                 "--image-format=png", "--props", json.dumps(props)]
    return _run(cmd, out_mp4, timeout_s, "scene render")


# convenience wrappers mirroring motion_graphics API -------------------------
def lower_third(workdir: str, name: str, role: str = "", W=1920, H=1080,
                dur_s=4.0, fps=30, accent="#00d9ff", out=None, **kw) -> str:
    out = out or os.path.join(workdir, f"rm_lt_{name[:10]}.webm")
    return render_clip("LowerThird", {"text": name, "role": role,
                                      "accent": accent, **kw}, out,
                       width=W, height=H, fps=fps,
                       duration_in_frames=int(dur_s * fps))


def stat_counter(workdir: str, value: float, label: str, W=1920, H=1080,
                 dur_s=3.0, fps=30, suffix="", color="#ffd23c", out=None, **kw) -> str:
    out = out or os.path.join(workdir, f"rm_stat_{int(value)}.webm")
    return render_clip("StatCounter", {"value": value, "text": label,
                                       "suffix": suffix, "accent": color, **kw},
                       out, width=W, height=H, fps=fps,
                       duration_in_frames=int(dur_s * fps))


def title_reveal(workdir: str, title: str, sub: str = "", W=1920, H=1080,
                 dur_s=4.0, fps=30, out=None, accent="#ff3d68", **kw) -> str:
    out = out or os.path.join(workdir, "rm_title.webm")
    return render_clip("KineticTitle", {"text": title, "sub": sub,
                                        "accent": accent, **kw}, out,
                       width=W, height=H, fps=fps,
                       duration_in_frames=int(dur_s * fps))


def chart_bars(workdir: str, data: list, labels=None, W=1920, H=1080,
               dur_s=3.5, fps=30, out=None, title="", accent="#00d9ff", **kw) -> str:
    out = out or os.path.join(workdir, "rm_chart.webm")
    return render_clip("BarChart", {"data": data, "labels": labels or [],
                                    "title": title, "accent": accent, **kw}, out,
                       width=W, height=H, fps=fps,
                       duration_in_frames=int(dur_s * fps))


def quote_card(workdir: str, quote: str, author: str = "", W=1920, H=1080,
               dur_s=5.0, fps=30, out=None, accent="#5aa2ff", **kw) -> str:
    out = out or os.path.join(workdir, "rm_quote.mp4")
    return render_clip("QuoteCard", {"text": quote, "author": author,
                                     "accent": accent, **kw}, out,
                       width=W, height=H, fps=fps, transparent=False,
                       duration_in_frames=int(dur_s * fps))


def subscribe_bumper(workdir: str, handle="@yourchannel", W=1920, H=1080,
                     dur_s=3.0, fps=30, out=None, **kw) -> str:
    out = out or os.path.join(workdir, "rm_sub.webm")
    return render_clip("SubscribeBumper", {"handle": handle, **kw}, out,
                       width=W, height=H, fps=fps,
                       duration_in_frames=int(dur_s * fps))


def status() -> dict:
    return {
        "node": node_bin() or "NOT FOUND",
        "project_dir": PROJ_DIR,
        "deps_installed": deps_installed(),
        "ready": available(),
        "compositions": {k: v[2] for k, v in COMPOSITIONS.items()},
    }
