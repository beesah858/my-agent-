"""VidForge AI - Motion Graphics Lab.

Programmatic After-Effects-style motion graphics rendered as transparent
ProRes4444/MOV overlays (via FFmpeg lavfi + PIL frame generation):
  lower thirds, stat counters, animated titles, callout arrows, progress rings,
  quote cards, map pings, chart bars/lines, subscribe bumpers, logo reveals.
Every generator returns a .mov clip that the timeline can overlay anywhere.
"""
from __future__ import annotations

import math
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

from .render_engine import ffmpeg_bin


def _font(size, bold=True):
    paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _frames_to_mov(frames_dir: str, out_mov: str, fps: int, dur_s: float):
    exe = ffmpeg_bin()
    subprocess.run([exe, "-y", "-hide_banner", "-loglevel", "error",
                    "-framerate", str(fps), "-i", os.path.join(frames_dir, "f_%04d.png"),
                    "-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p10le",
                    "-t", f"{dur_s:.3f}", out_mov], check=True)
    return out_mov


def _tmpdir(workdir: str, name: str) -> str:
    d = os.path.join(workdir, "mg_" + name)
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------- generators
def lower_third(workdir: str, name: str, role: str = "", W=1920, H=1080,
                dur_s=4.0, fps=30, accent=(0, 200, 255), out=None) -> str:
    fd = _tmpdir(workdir, "lt_" + name[:8])
    f1, f2 = _font(int(H * 0.055)), _font(int(H * 0.030))
    total = int(dur_s * fps)
    for i in range(total):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        t = i / total
        slide = min(1.0, t / 0.18)
        ease = 1 - (1 - slide) ** 3
        y = int(H * 0.78)
        x0 = int(-W * 0.5 + ease * (W * 0.5 + 80))
        bar_w = int(ease * (W * 0.42))
        d.rectangle([x0, y, x0 + bar_w, y + int(H * 0.012)], fill=accent + (230,))
        if slide >= 1:
            fade = min(1.0, (t - 0.18) / 0.12) if t > 0.18 else 0
            d.text((x0 + 10, y - int(H * 0.075)), name, font=f1,
                   fill=(255, 255, 255, int(255 * max(fade, slide))))
            if role:
                d.text((x0 + 12, y - int(H * 0.028)), role, font=f2,
                       fill=accent + (int(220 * max(fade, slide)),))
        if t > dur_s - 0.6 / dur_s:
            pass
        img.save(os.path.join(fd, f"f_{i:04d}.png"))
    out = out or os.path.join(workdir, "lower_third.mov")
    return _frames_to_mov(fd, out, fps, dur_s)


def stat_counter(workdir: str, value: float, label: str, W=1920, H=1080,
                 dur_s=3.0, fps=30, suffix="", color=(255, 210, 60), out=None) -> str:
    fd = _tmpdir(workdir, "stat")
    f_big, f_lbl = _font(int(H * 0.16)), _font(int(H * 0.045))
    total = int(dur_s * fps)
    for i in range(total):
        t = i / (total - 1)
        ease = 1 - (1 - min(t / 0.7, 1)) ** 4
        v = value * ease
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        txt = f"{v:,.0f}{suffix}" if value >= 100 else f"{v:.1f}{suffix}"
        alpha = int(255 * min(1, t / 0.15))
        tw = d.textlength(txt, font=f_big)
        d.text(((W - tw) / 2, H * 0.36), txt, font=f_big, fill=color + (alpha,))
        lw = d.textlength(label, font=f_lbl)
        d.text(((W - lw) / 2, H * 0.58), label, font=f_lbl, fill=(255, 255, 255, alpha))
        img.save(os.path.join(fd, f"f_{i:04d}.png"))
    out = out or os.path.join(workdir, "stat.mov")
    return _frames_to_mov(fd, out, fps, dur_s)


def title_reveal(workdir: str, title: str, sub: str = "", W=1920, H=1080,
                 dur_s=4.0, fps=30, out=None) -> str:
    fd = _tmpdir(workdir, "title")
    f_t = _font(int(H * 0.09))
    f_s = _font(int(H * 0.04))
    total = int(dur_s * fps)
    words = title.split()
    for i in range(total):
        t = i / total
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        line_h = int(H * 0.11)
        n_shown = max(1, int(t / 0.55 * len(words)))
        shown = " ".join(words[:n_shown])
        alpha = int(255 * min(1, t / 0.1))
        lines = _wrap(shown, d, f_t, W * 0.8)
        y0 = H // 2 - (len(lines) * line_h) // 2
        for li, ln in enumerate(lines):
            tw = d.textlength(ln, font=f_t)
            d.text(((W - tw) / 2, y0 + li * line_h), ln, font=f_t,
                   fill=(255, 255, 255, alpha))
        if sub and t > 0.5:
            sa = int(255 * min(1, (t - 0.5) / 0.25))
            sw = d.textlength(sub, font=f_s)
            d.text(((W - sw) / 2, y0 + len(lines) * line_h + 20), sub, font=f_s,
                   fill=(120, 200, 255, sa))
        img.save(os.path.join(fd, f"f_{i:04d}.png"))
    out = out or os.path.join(workdir, "title.mov")
    return _frames_to_mov(fd, out, fps, dur_s)


def chart_bars(workdir: str, data: list[float], labels: list[str] | None = None,
               W=1920, H=1080, dur_s=3.5, fps=30, out=None) -> str:
    fd = _tmpdir(workdir, "chart")
    f_l = _font(int(H * 0.03))
    total = int(dur_s * fps)
    mx = max(data) or 1
    bw = int(W * 0.7 / len(data))
    base_y = int(H * 0.75)
    cols = [(0, 180, 255), (255, 90, 90), (120, 230, 120), (255, 200, 60),
            (200, 120, 255), (255, 140, 60), (80, 220, 220), (240, 240, 240)]
    for i in range(total):
        t = i / total
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for bi, v in enumerate(data):
            grow = max(0.0, min(1.0, (t - bi * 0.08) / 0.35))
            hgt = int(v / mx * H * 0.45 * (1 - (1 - grow) ** 3))
            x = int(W * 0.15 + bi * bw)
            d.rectangle([x, base_y - hgt, x + int(bw * 0.7), base_y],
                        fill=cols[bi % len(cols)] + (220,))
            if labels and grow > 0.5:
                d.text((x, base_y + 12), labels[bi], font=f_l, fill=(255, 255, 255, 200))
        d.line([W * 0.13, base_y, W * 0.9, base_y], fill=(255, 255, 255, 120), width=3)
        img.save(os.path.join(fd, f"f_{i:04d}.png"))
    out = out or os.path.join(workdir, "chart.mov")
    return _frames_to_mov(fd, out, fps, dur_s)


def subscribe_bumper(workdir: str, handle="@yourchannel", W=1920, H=1080,
                     dur_s=3.0, fps=30, out=None) -> str:
    fd = _tmpdir(workdir, "sub")
    f1 = _font(int(H * 0.06))
    total = int(dur_s * fps)
    cx, cy = W // 2, int(H * 0.45)
    for i in range(total):
        t = i / total
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        pop = 1 + 0.25 * math.sin(min(t / 0.3, 1) * math.pi) if t < 0.35 else 1
        rr = int(H * 0.09 * pop)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(230, 30, 40, 235))
        d.polygon([(cx - rr * 0.35, cy), (cx + rr * 0.2, cy - rr * 0.45),
                   (cx + rr * 0.2, cy + rr * 0.45)], fill=(255, 255, 255, 255))
        bell_y = cy - rr * 1.6 * min(1, t / 0.5)
        if t > 0.45:
            d.text((cx - d.textlength(handle, font=f1) / 2, cy + rr + 30),
                   handle, font=f1, fill=(255, 255, 255, 255))
        img.save(os.path.join(fd, f"f_{i:04d}.png"))
    out = out or os.path.join(workdir, "bumper.mov")
    return _frames_to_mov(fd, out, fps, dur_s)


def quote_card(workdir: str, quote: str, author: str = "", W=1920, H=1080,
               dur_s=5.0, fps=30, out=None) -> str:
    fd = _tmpdir(workdir, "quote")
    f_q, f_a = _font(int(H * 0.05)), _font(int(H * 0.032))
    total = int(dur_s * fps)
    for i in range(total):
        t = i / total
        a = int(255 * min(1, t / 0.2))
        img = Image.new("RGBA", (W, H), (12, 14, 20, min(a, 200)))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([W * 0.12, H * 0.28, W * 0.88, H * 0.72], radius=28,
                            outline=(90, 160, 255, a), width=4)
        lines = _wrap("“" + quote + "”", d, f_q, W * 0.68)
        y = H * 0.33
        for ln in lines:
            d.text((W * 0.16, y), ln, font=f_q, fill=(255, 255, 255, a))
            y += int(H * 0.075)
        if author:
            d.text((W * 0.16, y + 10), "— " + author, font=f_a, fill=(140, 190, 255, a))
        img.save(os.path.join(fd, f"f_{i:04d}.png"))
    out = out or os.path.join(workdir, "quote.mov")
    return _frames_to_mov(fd, out, fps, dur_s)


def _wrap(text, d, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=font) <= maxw:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]
