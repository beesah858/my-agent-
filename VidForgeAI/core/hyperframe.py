"""VidForge AI — HYPERFRAME motion-graphics engine (Python facade).

HyperFrame is the premium layer built on top of Remotion (remotion/src/
hyperframe.tsx): dense, data-driven animated visual cards — stat walls, bento
dashboards, hero splits, comparison matrices, chart dashboards and scrolling
news tickers.  Every frame is described by plain JSON-ish props so the AI
director / MCP agent can compose professional graphics with one call.

Two output modes:
  * full-frame clip (opaque MP4)      -> drop straight onto the timeline as b-roll
  * transparent overlay (WebM alpha)  -> lay over existing footage like a HUD

Falls back gracefully to the PIL generator (motion_graphics.py) when Node /
Remotion deps are unavailable, so pipelines NEVER break.
"""
from __future__ import annotations

import logging
import os
from typing import Iterable

from . import config
from . import remotion_bridge as rm

log = logging.getLogger("vidforge.hyperframe")

LAYOUTS = rm.HF_LAYOUTS          # grid | statwall | bento | hero | compare | chartdash
TILE_TYPES = rm.HF_TILE_TYPES    # stat | bar | text | big | chip | list | image

_ACCENTS = ["#00d9ff", "#ff3d68", "#ffd23c", "#7cff5e", "#b46bff", "#ff8a3d"]


def _tile_stat(label, value, suffix="", color=None):
    return {"type": "stat", "label": str(label), "value": value,
            "suffix": suffix, **({"color": color} if color else {})}


def _tile_bar(label, data, labels=None, color=None):
    return {"type": "bar", "label": str(label), "data": list(data),
            "labels": list(labels or []), **({"color": color} if color else {})}


def _tile_text(text, big=False, color=None):
    return {"type": "big" if big else "text", "value": str(text),
            **({"color": color} if color else {})}


def _tile_list(title, rows, color=None):
    return {"type": "list", "label": str(title), "labels": [str(r) for r in rows],
            **({"color": color} if color else {})}


def _tile_chip(label, color=None):
    return {"type": "chip", "label": str(label),
            **({"color": color} if color else {})}


def _tile_image(src, caption=""):
    return {"type": "image", "value": src, "label": caption}


def build_props(title: str, items: list[dict], *, layout: str = "statwall",
                subtitle: str = "", accent: str = "#00d9ff",
                accent2: str = "#ff3d68", scene: dict | None = None,
                **kw) -> dict:
    """Assemble validated HyperFrame props from tile dicts."""
    clean = []
    for it in items or []:
        t = dict(it)
        t["type"] = (t.get("type") or "stat").lower()
        if t["type"] not in TILE_TYPES:
            t["type"] = "stat"
        clean.append(t)
    return {"layout": layout if layout in LAYOUTS else "statwall",
            "title": title, "subtitle": subtitle, "accent": accent,
            "accent2": accent2, "items": clean,
            "scene": scene or {"kind": "gradient", "from": "#101423", "to": "#05070c"},
            **kw}


# ------------------------------------------------------------------ renderers
def hyper_frame(workdir: str, title: str, items: list[dict], *,
                layout: str = "statwall", dur_s: float = 6.0,
                W: int = 1920, H: int = 1080, fps: int = 30,
                transparent: bool = False, out: str | None = None,
                progress=None, **prop_kw) -> str:
    """Render an animated HyperFrame dashboard card.

    transparent=True -> WebM alpha overlay you can composite on footage;
    otherwise an opaque gradient-backdrop MP4 usable as full b-roll scene.
    """
    props = build_props(title, items, layout=layout, **prop_kw)
    ext = ".webm" if transparent else ".mp4"
    out = out or os.path.join(workdir, f"hf_{abs(hash(title)) % 10**6}{ext}")
    if not rm.available():
        log.warning("HyperFrame: Remotion not ready — falling back to PIL chart/stat card")
        return _fallback_card(workdir, title, items, out=out, W=W, H=H,
                              dur_s=dur_s, fps=fps, transparent=transparent)
    try:
        return rm.render_clip("HyperFrame", props, out, width=W, height=H,
                              fps=fps, duration_in_frames=int(dur_s * fps),
                              transparent=transparent)
    except Exception as e:
        log.error("HyperFrame render failed (%s) — PIL fallback", e)
        return _fallback_card(workdir, title, items, out=out, W=W, H=H,
                              dur_s=dur_s, fps=fps, transparent=transparent)


def hyper_ticker(workdir: str, lines: Iterable[str], *, dur_s: float = 5.0,
                 W: int = 1920, H: int = 1080, fps: int = 30, speed: float = 2.0,
                 accent: str = "#ffd23c", transparent: bool = True,
                 out: str | None = None, **kw) -> str:
    """Scrolling news-style fact ticker (great lower-third band for stats/news)."""
    props = {"lines": [str(l) for l in lines], "accent": accent, "speed": speed,
             **({"scene": kw.pop("scene", None)} if kw.get("scene") else {}), **kw}
    ext = ".webm" if transparent else ".mp4"
    out = out or os.path.join(workdir, f"ticker_{abs(hash(tuple(props['lines']))) % 10**6}{ext}")
    if not rm.available():
        log.warning("HyperTicker: Remotion not ready — skipping to static text card")
        from . import motion_graphics as mg
        return mg.title_reveal(workdir, title=" •  ".join(list(props["lines"])[:3]),
                                W=W, H=H, dur_s=dur_s, fps=fps, out=out.replace(ext, ".mov"))
    try:
        return rm.render_clip("HyperTicker", props, out, width=W, height=H,
                              fps=fps, duration_in_frames=int(dur_s * fps),
                              transparent=transparent)
    except Exception as e:
        log.error("HyperTicker render failed (%s)", e)
        raise


def still_frame(workdir: str, title: str, items: list[dict], *,
                layout: str = "bento", frame: int = 120,
                W: int = 1920, H: int = 1080, out_png: str | None = None,
                **prop_kw) -> str:
    """One high-res PNG frame of a HyperFrame — thumbnails, chapter cards, PDFs."""
    props = build_props(title, items, layout=layout, **prop_kw)
    out_png = out_png or os.path.join(workdir, "hf_still.png")
    if not rm.available():
        raise RuntimeError("HyperFrame still needs Remotion setup (Motion Lab → Setup)")
    return rm.render_still("HyperFrame", props, out_png, width=W, height=H, frame=frame)


# ------------------------------------------------------------------ smart builders
def auto_scene_card(scene_script: dict, *, W=1920, H=1080, dur_s=6.0,
                    workdir: str = ".", fps=30) -> str:
    """Director helper: turn a script scene into a fitting HyperFrame card.

    Picks layout/tiles automatically from narration keywords & numbers so the
    AI can generate data-viz b-roll without hand-writing props.
    """
    import re
    narr = (scene_script.get("narration") or "")
    nums = [float(n.replace(",", "")) for n in re.findall(r"\b\d[\d,]*\.?\d*\b", narr)]
    words = re.findall(r"[A-Za-z][A-Za-z .&/-]{2,40}", narr)
    title = (scene_script.get("visual_query") or (words[0].strip().title() if words else "Facts"))[:48]
    items: list[dict] = []
    if len(nums) >= 3:
        items = [_tile_stat(f"Fact {i+1}", n,
                            color=_ACCENTS[i % len(_ACCENTS)])
                 for i, n in enumerate(nums[:6])]
        layout = "statwall"
    elif len(nums) == 2:
        items = [_tile_stat(nums[0] and f"{title}" or title, nums[0]),
                 _tile_text(narr[:110])]
        layout = "hero"
    elif nums:
        items = [_tile_stat(title, nums[0]),
                 _tile_list("Key points", [w.strip().title() for w in words[1:5]])]
        layout = "hero"
    else:
        items = [_tile_text(narr[:160], big=True)] + \
                [_tile_chip(w.strip().title()) for w in words[1:4]]
        layout = "grid"
    return hyper_frame(workdir, title, items, layout=layout,
                       dur_s=dur_s, W=W, H=H, fps=fps)


# ------------------------------------------------------------------ PIL fallback
def _fallback_card(workdir, title, items, *, out, W, H, dur_s, fps, transparent):
    """No-Node fallback: animated stat/list card via the built-in PIL engine."""
    from . import motion_graphics as mg
    first_stat = next((it for it in items if it.get("type") == "stat"), None)
    if first_stat:
        return mg.stat_counter(workdir, value=float(first_stat.get("value") or 0),
                               label=str(first_stat.get("label") or title)[:40],
                               W=W, H=H, dur_s=dur_s, fps=fps,
                               out=out.rsplit(".", 1)[0] + ".mov")
    return mg.title_reveal(workdir, title=title, sub="", W=W, H=H,
                           dur_s=dur_s, fps=fps, out=out.rsplit(".", 1)[0] + ".mov")


def status() -> dict:
    st = rm.status()
    st["hyperframe_ready"] = bool(st.get("ready"))
    st["layouts"] = LAYOUTS
    st["tile_types"] = TILE_TYPES
    return st
