"""VidForge AI - Caption template engine.

200+ CapCut-style caption presets generated procedurally from style families:
  pop (word-by-word bounce), karaoke (highlight sweep), neon glow, outline bold,
  typewriter, slide-up, shake impact, gradient box, minimal clean, meme top/bottom,
  subtitle broadcast, handwriting reveal ... x palettes x fonts x positions.

Each preset compiles to ASS (Advanced SubStation Alpha) so the render gets true
per-word animation synced with the narration word timestamps.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field

# ------------------------------------------------------------------ vocabulary
FONTS = ["Arial", "Arial Black", "Impact", "Verdana", "Georgia", "Trebuchet MS",
         "Comic Sans MS", "Segoe UI", "Courier New", "Palatino Linotype"]
PALETTES = {
    "white": ("&H00FFFFFF", "&H00000000"),
    "yellow_pop": ("&H0000E5FF", "&H00000000"),
    "cyan_neon": ("&H00FFE3A1", "&H00000000"),
    "hot_pink": ("&H006AB4FF", "&H00000000"),
    "mint": ("&H00A9E8B8", "&H00000000"),
    "karaoke_bw": ("&H00FFFFFF", "&H002A2A2A"),   # active -> white, dim -> grey
    "fire": ("&H001F7BFF", "&H00000000"),
    "ice": ("&H00FFCF9A", "&H00101010"),
    "gold_lux": ("&H0000D7FF", "&H00000050"),
    "matrix": ("&H0000FF5E", "&H00000000"),
    "vaporwave": ("&H00FF6AD5", "&H00000000"),
    "royal": ("&H00FF80C8", "&H00000000"),
}
FAMILIES = [
    ("Pop Bounce", "pop"), ("Karaoke Sweep", "karaoke"), ("Neon Glow", "neon"),
    ("Bold Outline", "outline"), ("Typewriter", "typewriter"), ("Slide Up", "slide"),
    ("Shake Impact", "shake"), ("Box Gradient", "box"), ("Minimal Clean", "minimal"),
    ("Meme Classic", "meme"), ("Broadcast Lower-Third", "lower3rd"),
    ("Zoom Punch", "zoom"), ("Fade Cinematic", "fade"), ("Wave Motion", "wave"),
    ("Drop In", "drop"), ("Flip Reveal", "flip"),
]
POSITIONS = [("bottom", "&H00;\\an2"), ("center", "&H00;\\an5"),
             ("top", "&H00;\\an8"), ("lower-third", "&H00;\\an2")]


@dataclass
class CaptionPreset:
    id: str
    name: str
    family: str
    font: str
    size_pct: float          # % of frame height
    palette: str
    position: str
    bold: bool
    italic: bool
    border_px: int
    shadow_px: int
    anim: str
    per_word: bool
    secondary_color: str | None = None
    background: str | None = None


def build_library() -> list[CaptionPreset]:
    """16 animation families x 12 palettes x font/size/position variants = 200+ presets."""
    lib: list[CaptionPreset] = []
    rnd = random.Random(42)                      # deterministic library
    pal_keys = list(PALETTES.keys())
    idx = 0
    for fam_name, anim in FAMILIES:
        for pi, pal in enumerate(pal_keys):      # 12 palettes per family
            for vi in range(2):                  # 2 layout variants each => 384 total
                font = FONTS[(idx + vi * 3) % len(FONTS)]
                pos = POSITIONS[(pi + vi + FAMILIES.index((fam_name, anim))) % len(POSITIONS)][0]
                size = 4.5 + ((idx // 2) % 5) * 0.9   # 4.5%..8.1% of height
                lib.append(CaptionPreset(
                    id=f"{anim}-{pal}-{idx:03d}",
                    name=f"{fam_name} · {pal.replace('_',' ').title()} {vi+1}",
                    family=fam_name, font=font, size_pct=size, palette=pal,
                    position=pos, bold=anim in ("pop", "karaoke", "outline", "meme", "zoom", "shake"),
                    italic=anim == "fade", border_px=3 if anim in ("outline", "meme", "pop") else 1,
                    shadow_px=2 if anim in ("neon", "fade") else 0,
                    anim=anim, per_word=anim in ("pop", "karaoke", "typewriter", "zoom",
                                                 "wave", "drop", "flip", "shake"),
                    secondary_color=PALETTES[pal][1] if anim == "karaoke" else None,
                    background="&HAA202020" if anim == "box" else None,
                ))
                idx += 1
    return lib


LIBRARY = build_library()
_BY_ID = {p.id: p for p in LIBRARY}
DEFAULT_SHORT_PRESET = next(p.id for p in LIBRARY if p.anim == "pop")
DEFAULT_LONG_PRESET = next(p.id for p in LIBRARY if p.anim == "karaoke")


def get_preset(preset_id: str) -> CaptionPreset:
    if preset_id in _BY_ID:
        return _BY_ID[preset_id]
    # custom presets saved by user live in JSON next to config
    try:
        custom_file = os.path.join(os.path.dirname(__file__), "..", "data", "custom_captions.json")
        if os.path.exists(custom_file):
            with open(custom_file, encoding="utf-8") as f:
                customs = json.load(f)
            for c in customs:
                if c.get("id") == preset_id:
                    return CaptionPreset(**c)
    except Exception:
        pass
    raise KeyError(f"unknown caption preset {preset_id}")


def save_custom_preset(p: CaptionPreset) -> None:
    custom_file = os.path.join(os.path.dirname(__file__), "..", "data", "custom_captions.json")
    customs = []
    if os.path.exists(custom_file):
        with open(custom_file, encoding="utf-8") as f:
            customs = json.load(f)
    customs = [c for c in customs if c.get("id") != p.id]
    from dataclasses import asdict
    customs.append(asdict(p))
    with open(custom_file, "w", encoding="utf-8") as f:
        json.dump(customs, f, indent=2)


# ------------------------------------------------------------------ ASS writer
_HDR = """[Script Info]
Title: VidForge AI captions
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {w}
PlayResY: {h}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{fsize},{pcolor},{scolor},{ocolor},&H88000000,{bold},{italic},0,0,100,100,0,0,{bstyle},{border},{shadow},{align},40,40,{marginv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(ms: float) -> str:
    s = ms / 1000.0
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{sec:05.2f}".replace(".", ":").zfill(11)


def _esc(t: str) -> str:
    return t.replace("{", "(").replace("}", ")").replace("\n", "\\N")


def words_to_lines(words: list[dict], max_words: int = 6) -> list[list[dict]]:
    lines, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return lines


def render_ass(preset_id: str, width: int, height: int,
               words: list[dict], *, line_duration_hint_ms: int = 0) -> str:
    """Compile word timestamps -> animated ASS subtitle text."""
    p = get_preset(preset_id)
    pc, oc = PALETTES.get(p.palette, PALETTES["white"])
    scolor = p.secondary_color or "&H00000000"
    fsize = int(height * p.size_pct / 100)
    align_map = {"bottom": 2, "center": 5, "top": 8, "lower-third": 2}
    align = align_map[p.position]
    marginv = int(height * (0.10 if p.position in ("bottom", "lower-third") else
                           0.06 if p.position == "top" else 0))
    bstyle = 3 if p.background else 1
    hdr = _HDR.format(w=width, h=height, font=p.font, fsize=fsize,
                      pcolor=pc, scolor=scolor, ocolor=oc,
                      bold=-1 if p.bold else 0, italic=-1 if p.italic else 0,
                      bstyle=bstyle, border=p.border_px, shadow=p.shadow_px,
                      align=align, marginv=marginv)
    ev = [hdr]
    if not words:
        return "\n".join(ev)

    lines = words_to_lines(words, max_words=5 if p.per_word else 9)
    for ln in lines:
        start, end = ln[0]["start_ms"], ln[-1]["end_ms"] + 250
        if not p.per_word:
            text = " ".join(_esc(w["text"]) for w in ln)
            tag = _line_tag(p, dur_ms=end - start)
            ev.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{tag}{text}")
        else:
            # karaoke / per-word animation
            parts = []
            for w in ln:
                wt = _esc(w["text"])
                d = w["end_ms"] - w["start_ms"]
                pre = _word_tag(p, d)
                parts.append(f"{pre}{{{wt}}}" if False else f"{pre}{wt}")
            joined = " ".join(parts)
            ev.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{joined}")
    return "\n".join(ev) + "\n"


def _line_tag(p: CaptionPreset, dur_ms: int) -> str:
    a = p.anim
    if a == "fade":
        return r"{\fad(500,400)}"
    if a == "typewriter":
        n = max(1, dur_ms // 45)
        return r"{\k%d}" % n
    if a == "slide":
        return r"{\t(0,250)\move(0,%d,0,0)}" % 60
    if a == "lower3rd":
        return r"{\t(0,300)\pos(80,\y)\clip(0,0,0,0)\t(300,700)\clip(0,0,1920,1080)}"
    if a == "meme":
        return r"{\frz0\b1\fsp2}"
    return r"{\fad(120,120)}"


def _word_tag(p: CaptionPreset, wdur_ms: int) -> str:
    a, half = p.anim, max(40, wdur_ms // 2)
    if a == "pop":
        return (r"{\t(0,%d)\fscx130\fscy130\t(%d,%d)\fscx100\fscy100}"
                % (half, half, wdur_ms))
    if a == "karaoke":
        return r"{\kf%d}" % max(1, wdur_ms // 10)
    if a == "neon":
        return r"{\t(0,%d)\bord5\xshad30\bord1\b1\fscy105\t(%d,%d)\fscy100\bord%d}" % (
            half, half, wdur_ms, p.border_px)
    if a == "zoom":
        return r"{\t(0,%d)\fscx180\fscy180\t(%d,%d)\fscx100\fscy100}" % (half, half, wdur_ms)
    if a == "shake":
        return (r"{\t(0,%d)\pos(0,-8)\t(%d,%d)\pos(0,6)\t(%d,%d)\pos(0,0)}"
                % (half // 3, half // 3, 2 * half // 3, 2 * half // 3, half))
    if a == "wave":
        return r"{\t(0,%d)\fy6\pos(x,y-14)\t(%d,%d)\fy0\pos(x,y)}" % (half, half, wdur_ms)
    if a == "drop":
        return r"{\fscx100\t(0,%d)\move(0,-120,0,0,0,%d)}" % (wdur_ms, wdur_ms)
    if a == "flip":
        return r"{\t(0,%d)\fry90\t(%d,%d)\fry0}" % (half, half, wdur_ms)
    if a == "typewriter":
        return r"{\k%d}" % max(1, wdur_ms // 10)
    if a == "box":
        return r"{\fad(80,80)}"
    return r"{\fad(90,90)}"


def preview_png(preset_id: str, out_png: str, sample: str = "This is your caption"):
    """Render a quick PNG preview of a preset using PIL."""
    from PIL import Image, ImageDraw, ImageFont
    p = get_preset(preset_id)
    W, H = 640, 360
    img = Image.new("RGB", (W, H), (18, 18, 24))
    d = ImageDraw.Draw(img)
    fs = int(H * p.size_pct / 100)
    try:
        fp = ImageFont.truetype(_find_font(p.font), fs)
    except Exception:
        fp = ImageFont.load_default()
    pc_hex = PALETTES.get(p.palette, ("&H00FFFFFF",))[0][-6:]  # BBGGRR hex
    pc_rgb = tuple(int(pc_hex[i:i + 2], 16) for i in (4, 2, 0))
    bbox = d.textbbox((0, 0), sample, font=fp)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    y = {"bottom": H - th - 40, "center": (H - th) // 2,
         "top": 40, "lower-third": H - th - 70}[p.position]
    ob_hex = PALETTES.get(p.palette, ("", "&H00000000"))[1][-6:]
    ob_rgb = tuple(int(ob_hex[i:i + 2], 16) for i in (4, 2, 0))
    d.text(((W - tw) // 2, y), sample, font=fp, fill=pc_rgb,
           stroke_width=p.border_px, stroke_fill=ob_rgb)
    d.rectangle([10, 10, 120, 30], fill=(30, 30, 40))
    d.text((14, 12), p.family.split(" ")[0], fill=(160, 160, 255))
    img.save(out_png)
    return out_png


def _find_font(name: str) -> str:
    base = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    win = rf"C:\Windows\Fonts\{name.lower().replace(' ', '')}.ttf"
    for cand in (win, f"C:\\Windows\\Fonts\\{name}.ttf", base):
        if os.path.exists(cand):
            return cand
    return base
