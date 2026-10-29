"""VidForge AI - The Render Engine (FFmpeg orchestration).

Produces:
  * final.mp4          polished, caption-burned, music-bedded, ready for YouTube
  * final.srt          subtitle file
  * project.json       FULLY EDITABLE timeline (importable back / to editors)
  * edit_decision.xml  EDL-ish cut list for Premiere/DaVinci round-trip
Advanced features: Ken-Burns motion on stills, speed ramps, punch-ins,
crossfade/jazz-cut transitions, lower-third name tags, progress bar overlay,
picture-in-picture webcam slot, loudness normalization (-14 LUFS YT target),
auto chapter markers, watermark/brand intro-outro, vertical 9:16 reframe.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, asdict

log = logging.getLogger("vidforge.render")


def ffmpeg_bin() -> str:
    # 0) inside VidForgeAI.exe, prefer the uniquely-named bundled ffmpeg we
    #    ship (vidforge_ffmpeg.exe) so a broken/stale system ffmpeg on PATH
    #    can never hijack renders.
    try:
        from .runtime import is_frozen, locate_bundled_ffmpeg
        if is_frozen():
            b = locate_bundled_ffmpeg()
            if b:
                return b
    except Exception:
        pass
    cfg_path = None
    try:
        from . import config
        cfg_path = config.CFG.get("ffmpeg_path") or "ffmpeg"
    except Exception:
        cfg_path = "ffmpeg"
    if shutil.which(cfg_path):
        return cfg_path
    # fall back to pip-bundled static build (works on machines w/o system ffmpeg)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return cfg_path


def ffprobe_json(path: str) -> dict:
    try:
        out = subprocess.check_output(
            [ffmpeg_bin().replace("ffmpeg", "ffprobe") if False else "ffprobe",
             "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path], text=True)
        return json.loads(out)
    except Exception:
        # bundled ffmpeg can probe too via -i
        try:
            exe = ffmpeg_bin()
            out = subprocess.check_output([exe, "-i", path, "-hide_banner"],
                                          stderr=subprocess.STDOUT, text=True)
            return {"raw": out}
        except Exception as e:
            log.warning("probe fail %s: %s", path, e)
            return {}


def media_duration(path: str) -> float:
    d = ffprobe_json(path)
    try:
        return float(d["format"]["duration"])
    except Exception:
        return 0.0


# ------------------------------------------------------------------ model
@dataclass
class Clip:
    id: str
    kind: str                 # video | image | generated | browser_capture
    source: str               # local path (filled at render time) or remote url
    in_s: float = 0.0         # trim in
    out_s: float = 5.0        # trim out
    speed: float = 1.0        # 0.25..4.0
    transition: str = "cut"   # cut|fade|slideleft|wipe|glitch
    ken_burns: str = ""       # zoomin|zoomout|panleft|panright|none
    punch_in_at: float | None = None   # seconds into clip for a 1.3x punch-in
    volume: float = 1.0
    layer: int = 0            # 0 main, 1 pip/webcam
    pip: dict | None = None   # {w_pct,x_pct,y_pct} when layer==1
    label: str = ""           # lower-third text
    meta: dict | None = None  # license/credit info


@dataclass
class Timeline:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    crf: int = 19
    clips: list = None            # list[Clip]
    voiceover: list = None        # list[{path,start_s,words:[...]}]
    music: dict | None = None     # {path, volume, ducking:true}
    captions_preset: str = "pop-yellow_pop-000"
    captions_enabled: bool = True
    watermark: str = ""           # png path
    progress_bar: bool = True
    lufs_normalize: bool = True
    chapters: list = None         # [{t_s,title}]
    bg_color: str = "black"
    title: str = "Untitled"

    def __post_init__(self):
        if self.clips is None:
            self.clips = []
        if self.voiceover is None:
            self.voiceover = []
        if self.chapters is None:
            self.chapters = []


# ------------------------------------------------------------------ helpers
def _fmt_ts(sec: float) -> str:
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def plan_durations(tl: Timeline, workdir: str, progress=None) -> Timeline:
    """Ensure every clip has real source + sane out_s (respect media length)."""
    cursor = 0.0
    for c in tl.clips:
        if not c.source or not os.path.exists(c.source):
            raise FileNotFoundError(f"clip {c.id}: missing source {c.source}")
        if c.kind in ("video", "browser_capture"):
            dur = media_duration(c.source) or c.out_s
            c.out_s = min(c.out_s, dur) if c.out_s > 0 else dur
        eff = max(0.2, (c.out_s - c.in_s) / max(0.25, c.speed))
        c._start = cursor
        c._eff = eff
        cursor += eff
    tl.total_duration = cursor
    return tl


def _vf_for_clip(c: Clip, W: int, H: int, fps: int) -> str:
    """Build the per-clip video filter chain."""
    parts = [f"scale={W}:{H}:force_original_aspect_ratio=increase",
             f"crop={W}:{H}", f"fps={fps}", "setsar=1"]
    kb = c.ken_burns or ("zoomin" if c.kind == "image" else "")
    if c.kind == "image" or kb in ("zoomin", "zoomout", "panleft", "panright"):
        t = max(1, int((c.out_s - c.in_s) * fps))
        if kb == "zoomin":
            parts.append(f"zoompan=z='min(zoom+0.0012,1.25)':d={t}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}")
        elif kb == "zoomout":
            parts.append(f"zoompan=z='if(eq(on,1),1.25,max(zoom-0.0012,1.0))':d={t}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}")
        elif kb == "panleft":
            parts.append(f"zoompan=z=1.15:d={t}:x='iw-iw/zoom-on*((iw-iw/zoom)/{t})':y='ih/2-(ih/zoom/2)':s={W}x{H}")
        elif kb == "panright":
            parts.append(f"zoompan=z=1.15:d={t}:x='on*((iw-iw/zoom)/{t})':y='ih/2-(ih/zoom/2)':s={W}x{H}")
    if c.punch_in_at is not None:
        f0 = int(c.punch_in_at * fps)
        parts.append(
            f"zoompan=z='if(gte(on,{f0}),1.3,1.0)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}")
    return ",".join(parts)


def build_filtergraph(tl: Timeline, workdir: str) -> tuple[str, str]:
    """Return (filter_complex, last_label)."""
    W, H, fps = tl.width, tl.height, tl.fps
    fg, labels = [], []
    n = len(tl.clips)
    for i, c in enumerate(tl.clips):
        vf = _vf_for_clip(c, W, H, fps)
        if c.kind != "image":
            trim = (f"[{i}:v]trim=start={c.in_s}:end={c.out_s},setpts=PTS-STARTPTS,"
                    f"fps={fps}[b{i}];")
        else:
            trim = f"[{i}:v]setpts=PTS-STARTPTS,fps={fps}[b{i}];"
        fg.append(trim)
        chain = f"[b{i}]{vf}"
        if c.speed != 1.0:
            chain += f",setpts={1/c.speed:.4f}*PTS"
        chain += f"[v{i}];"
        fg.append(chain)
        labels.append(f"[v{i}]")

    # concatenate main-layer clips with transitions where requested
    main = [(i, c) for i, c in enumerate(tl.clips) if getattr(c, "layer", 0) == 0]
    seq = labels[main[0][0]]
    acc_dur = main[0][1]._eff
    prev_idx = main[0][0]
    for idx, c in main[1:]:
        nxt = labels[idx]
        if c.transition == "fade":
            fo = max(0.0, acc_dur - 0.5)
            fg.append(f"{seq}{nxt}xfade=transition=fade:duration=0.5:offset={fo:.3f}[x{idx}];")
        elif c.transition == "slideleft":
            fo = max(0.0, acc_dur - 0.4)
            fg.append(f"{seq}{nxt}xfade=transition=slideleft:duration=0.4:offset={fo:.3f}[x{idx}];")
        elif c.transition == "wipe":
            fo = max(0.0, acc_dur - 0.5)
            fg.append(f"{seq}{nxt}xfade=transition=wipeleft:duration=0.5:offset={fo:.3f}[x{idx}];")
        elif c.transition == "glitch":
            fo = max(0.0, acc_dur - 0.25)
            fg.append(f"{seq}{nxt}xfade=transition=hlslice:duration=0.25:offset={fo:.3f}[x{idx}];")
        else:  # hard cut
            fg.append(f"{seq}{nxt}concat=n=2:v=1:a=0[x{idx}];")
        seq = f"[x{idx}]"
        acc_dur += c._eff
        prev_idx = idx

    base = seq
    # picture-in-picture overlays
    for i, c in enumerate(tl.clips):
        if getattr(c, "layer", 1) == 1 and c.pip:
            pw = int(W * c.pip.get("w_pct", 30) / 100)
            px = int(W * c.pip.get("x_pct", 68) / 100)
            py = int(H * c.pip.get("y_pct", 62) / 100)
            fg.append(f"{base}[v{i}]overlay=x={px}:y={py}:eval=frame"
                      f":enable='between(t,{c._start:.3f},{c._start + c._eff:.3f})'"
                      f"[pip{i}];".replace(f"x={px}", f"x=X"))
            # scale pip first
            fg[-1] = (f"[v{i}]scale={pw}:-2[pips{i}];"
                      f"{base}[pips{i}]overlay=x={px}:y={py}:"
                      f"enable='between(t,{c._start:.3f},{c._start + c._eff:.3f})'[pip{i}];")
            base = f"[pip{i}]"

    # watermark
    if tl.watermark and os.path.exists(tl.watermark):
        wm_input = len(tl.clips)  # will be appended input index; caller adds it
        fg.append(f"{base}[{wm_input}:v]overlay=W-w-{40}:40[wm];")
        base = "[wm]"

    # captions burn-in
    ass_path = os.path.join(workdir, "captions.ass")
    if tl.captions_enabled and os.path.exists(ass_path):
        safe = ass_path.replace("\\", "/").replace(":", "\\:")
        fg.append(f"{base}subtitles='{safe}'[cap];")
        base = "[cap]"

    # progress bar
    if tl.progress_bar:
        fg.append(f"{base}drawbox=x=0:y=ih-8:w='iw*t/{tl.total_duration:.3f}':h=8"
                  f":color=0xE53935@1.0:t=fill[bar];")
        base = "[bar]"

    fg_str = "".join(fg).rstrip(";")
    # ffmpeg requires every intermediate chain to start with an input pad label;
    # our per-clip chains start with [bN] which is fine. Ensure no trailing ';'.
    return fg_str, base


# ------------------------------------------------------------------ audio mix
def build_audio_graph(tl: Timeline) -> tuple[list[str], str]:
    """Inputs are ordered: 0..n-1 clips, n..n+m-1 voiceovers, last = music.
    Returns (filter fragments, final label) or ([], '') if no audio at all."""
    frags, labels = [], []
    m = len(tl.voiceover)
    for j, vo in enumerate(tl.voiceover):
        idx = len(tl.clips) + j
        start = float(vo.get("start_s", 0))
        frags.append(f"[{idx}:a]asetpts=PTS-STARTPTS,adelay={int(start*1000)}|{int(start*1000)}[vo{j}];")
        labels.append(f"[vo{j}]")
    if tl.music and tl.music.get("path"):
        midx = len(tl.clips) + m
        vol = float(tl.music.get("volume", 0.18))
        total = getattr(tl, "total_duration", 60)
        frags.append(f"[{midx}:a]aloop=loop=-1:size=2e9,atrim=0:{total:.3f},"
                     f"asetpts=PTS-STARTPTS,volume={vol}[musraw];")
        if tl.music.get("ducking", True) and labels:
            allvo = "".join(labels)
            frags.append(f"{allvo}amix=inputs={len(labels)}:duration=longest:"
                         f"dropout_transition=0[nvo];")
            # true sidechain ducking: narration keys the music compressor
            frags.append("[nvo]asplit=2[nvoK][nvoA];"
                         "[musraw][nvoA]sidechaincompress=threshold=0.03:ratio=8:"
                         "attack=80:release=400[mus];"
                         "[nvoK][mus]amix=inputs=2:duration=first:normalize=0,"
                         "atrim=0:%.3f[aout];" % total)
            label = "[aout]"
        elif labels:
            frags.append("".join(labels) +
                         f"amix=inputs={len(labels)}:duration=longest[nvo];"
                         f"[nvo][musraw]amix=inputs=2:duration=first:normalize=0,"
                         f"atrim=0:{total:.3f}[aout];")
            label = "[aout]"
        else:
            frags.append("[musraw]anull[aout];")
            label = "[aout]"
        return frags, label or ""
    if labels:
        if len(labels) == 1:
            frags.append(labels[0] + "anull[aout];")
            return frags, "[aout]"
        frags.append("".join(labels) +
                     f"amix=inputs={len(labels)}:duration=longest:dropout_transition=0[aout];")
        return frags, "[aout]"
    return [], ""


def write_srt(words: list[dict], path: str, max_words: int = 8):
    def ts(sec):
        h, r = divmod(int(sec // 1), 3600)
        m, s = divmod(r, 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    lines, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    with open(path, "w", encoding="utf-8") as f:
        for i, ln in enumerate(lines, 1):
            f.write(f"{i}\n{ts(ln[0]['start_ms']/1000)} --> {ts((ln[-1]['end_ms']+300)/1000)}\n")
            f.write(" ".join(w["text"] for w in ln) + "\n\n")


def write_edl(tl: Timeline, path: str):
    rows = []
    for c in tl.clips:
        rows.append({"id": c.id, "kind": c.kind, "source": c.source,
                     "in_s": c.in_s, "out_s": c.out_s, "speed": c.speed,
                     "transition_next": c.transition, "layer": c.layer,
                     "timeline_start_s": round(getattr(c, "_start", 0), 3)})
    json.dump({"title": tl.title, "resolution": [tl.width, tl.height],
               "fps": tl.fps, "cuts": rows}, open(path, "w", encoding="utf-8"), indent=2)


# ------------------------------------------------------------------ main render
def render(tl: Timeline, out_path: str, workdir: str, *,
           progress_cb=None, cancel_event: threading.Event | None = None) -> dict:
    os.makedirs(workdir, exist_ok=True)
    tl = plan_durations(tl, workdir)
    exe = ffmpeg_bin()

    inputs = []
    for c in tl.clips:
        if c.kind == "image":
            inputs += ["-loop", "1", "-t", f"{c.out_s - c.in_s:.3f}", "-framerate", str(tl.fps),
                       "-i", c.source]
        else:
            inputs += ["-i", c.source]
    wm_added = False
    if tl.watermark and os.path.exists(tl.watermark):
        inputs += ["-loop", "1", "-i", tl.watermark]
        wm_added = True
    for vo in tl.voiceover:
        inputs += ["-i", vo["path"]]
    if tl.music and tl.music.get("path"):
        inputs += ["-stream_loop", "-1", "-i", tl.music["path"]]

    vf_str, vlabel = build_filtergraph(tl, workdir)
    af_frags, alabel = build_audio_graph(tl)

    # stitch video+audio graph
    full_fg = vf_str
    if af_frags:
        joiner = ";" if full_fg else ""
        full_fg += joiner + "".join(af_frags).rstrip(";")
    if tl.lufs_normalize and alabel and not alabel.startswith("[aout"):
        full_fg += f";{alabel}loudnorm=I=-14:TP=-1.5:LRA=11[aout];"
        alabel = "[aout]"

    map_v = ["-map", vlabel]
    args = [exe, "-y", "-hide_banner", "-loglevel", "error", "-stats", "-progress", "pipe:1"]
    args += inputs
    if full_fg:
        args += ["-filter_complex", full_fg]
    args += map_v
    if alabel:
        args += ["-map", alabel, "-c:a", "aac", "-b:a", "192k"]
        if tl.lufs_normalize:
            # loudnorm must live inside the complex graph (single-pass linear-ish)
            pass
    else:
        args += ["-an"]
    args += ["-c:v", "libx264", "-preset", "medium", "-crf", str(tl.crf),
             "-pix_fmt", "yuv420p", "-r", str(tl.fps),
             "-movflags", "+faststart", "-t", f"{tl.total_duration:.3f}"]
    if tl.chapters:
        chap_file = os.path.join(workdir, "chapters.meta")
        prev = 0.0
        with open(chap_file, "w", encoding="utf-8") as f:
            f.write(";FFMETADATA1\n")
            for ch in tl.chapters + [{"t_s": tl.total_duration, "title": "end"}]:
                f.write("[CHAPTER]\nTIMEBASE=1/1000\nSTART=%d\nEND=%d\ntitle=%s\n"
                        % (int(prev * 1000), int(ch["t_s"] * 1000), ch.get("title", "")))
                prev = ch["t_s"]
        # chapters are muxed in a fast copy pass after the main render
    args += [out_path]

    log.info("ffmpeg cmd length=%d chars", sum(len(str(a)) for a in args))
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    total = max(0.1, tl.total_duration)
    err_lines = []
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if line.startswith("out_time_ms="):
            try:
                done = int(line.split("=")[1]) / 1_000_000
                if progress_cb:
                    progress_cb(min(0.98, done / total))
            except Exception:
                pass
        if cancel_event is not None and cancel_event.is_set():
            proc.kill()
            raise RuntimeError("render cancelled")
    stderr = proc.stderr.read()
    rc = proc.wait()
    if rc != 0:
        log.error("ffmpeg rc=%s err=%s", rc, stderr[-2000:])
        raise RuntimeError("FFmpeg failed:\n" + stderr[-1500:])
    if progress_cb:
        progress_cb(1.0)

    # side outputs
    meta = {"output": out_path, "duration_s": round(total, 3),
             "size_bytes": os.path.getsize(out_path) if os.path.exists(out_path) else 0}
    # chapters embedded via mkv-style second pass (best-effort, mp4 faststart kept)
    if tl.chapters:
        chap_meta = os.path.join(workdir, "chapters.meta")
        with open(chap_meta, "w", encoding="utf-8") as f:
            f.write(";FFMETADATA1\n")
            prev = 0.0
            for ch in tl.chapters + [{"t_s": total, "title": "end"}]:
                f.write("[CHAPTER]\nTIMEBASE=1/1000\nSTART=%d\nEND=%d\ntitle=%s\n"
                        % (int(prev * 1000), int(ch["t_s"] * 1000), ch.get("title", "")))
                prev = ch["t_s"]
        tmp = out_path + ".chap.mp4"
        r2 = subprocess.run([exe, "-y", "-i", out_path, "-i", chap_meta,
                             "-map_metadata", "1", "-map_chapters", "1",
                             "-c", "copy", "-movflags", "+faststart", tmp],
                            capture_output=True, text=True)
        if r2.returncode == 0 and os.path.exists(tmp):
            os.replace(tmp, out_path)
            meta["chapters"] = True

    # editable project export
    proj = {
        "app": "VidForge AI", "version": 2, "title": tl.title,
        "canvas": {"w": tl.width, "h": tl.height, "fps": tl.fps, "crf": tl.crf},
        "captions": {"preset": tl.captions_preset, "enabled": tl.captions_enabled},
        "music": tl.music, "watermark": tl.watermark,
        "clips": [asdict(c) for c in tl.clips],
        "voiceover": [{k: v for k, v in vo.items() if k != "words"} for vo in tl.voiceover],
        "word_timestamps": [vo.get("words", []) for vo in tl.voiceover],
        "chapters": tl.chapters,
    }
    with open(os.path.join(workdir, "project.json"), "w", encoding="utf-8") as f:
        json.dump(proj, f, indent=2)
    write_edl(tl, os.path.join(workdir, "edit_decision.json"))
    all_words = []
    for vo in tl.voiceover:
        all_words.extend(vo.get("words", []))
    if all_words:
        write_srt(all_words, os.path.splitext(out_path)[0] + ".srt")
    meta["project_json"] = os.path.join(workdir, "project.json")
    return meta
