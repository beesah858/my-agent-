"""VidForge AI - The AI Director pipeline (magic-light-style text-to-video).

Given just an idea + target length + format, it will:
 1. research the topic (LLM if configured, else built-in heuristic writer)
 2. write a professional script split into scenes (hook / body / CTA)
 3. synthesize narration per scene with word timestamps (hardened Edge-TTS)
 4. AUTO-SYNC visuals to speech: each scene's footage duration = its VO duration
    (this is what makes "jo bola wahi dikhe" true frame-for-frame)
 5. source b-roll: royalty-free APIs -> built-in browser -> generated MG overlay
 6. build the timeline (transitions, ken-burns, captions preset, music ducking)
 7. render final.mp4 + .srt + chapters + fully editable project.json
Works with zero API keys (LLM falls back to local template director).
"""
from __future__ import annotations

import json
import logging
import os
import re
import textwrap
import time
import uuid

from . import config, captions, media_search, motion_graphics as mg, tts_engine
from .render_engine import Clip, Timeline, render, media_duration

log = logging.getLogger("vidforge.director")

FORMATS = {
    "short": {"w": 1080, "h": 1920, "max_s": 62, "words_per_s": 2.9},
    "long": {"w": 1920, "h": 1080, "max_s": 900, "words_per_s": 2.5},
}


# ------------------------------------------------------------------ LLM brain
def llm(prompt: str, system: str = "", max_tokens: int = 2000) -> str | None:
    cfg = config.CFG
    to = int(cfg.get("llm_timeout_s", 120))
    try:
        if cfg["llm_provider"] == "openai" and cfg.get("openai_api_key"):
            import requests
            r = requests.post("https://api.openai.com/v1/chat/completions",
                              headers={"Authorization": f"Bearer {cfg['openai_api_key']}"},
                              json={"model": cfg["openai_model"],
                                    "messages": [{"role": "system", "content": system or "You are a world-class video director."},
                                                 {"role": "user", "content": prompt}],
                                    "temperature": 0.7, "max_tokens": max_tokens}, timeout=to)
            return r.json()["choices"][0]["message"]["content"]
        if cfg["llm_provider"] == "openai" and cfg.get("openai_base_url"):
            # custom / local OpenAI-compatible endpoint (LM Studio, Jan, vLLM, Groq…)
            import requests
            base = cfg["openai_base_url"].rstrip("/")
            r = requests.post(base + "/chat/completions",
                              headers={"Authorization": f"Bearer {cfg.get('openai_api_key') or 'not-needed'}"},
                              json={"model": cfg["openai_model"],
                                    "messages": [{"role": "system", "content": system or "You are a world-class video director."},
                                                 {"role": "user", "content": prompt}],
                                    "temperature": 0.7, "max_tokens": max_tokens}, timeout=to)
            return r.json()["choices"][0]["message"]["content"]
        if cfg["llm_provider"] == "anthropic" and cfg.get("anthropic_api_key"):
            import requests
            r = requests.post("https://api.anthropic.com/v1/messages",
                              headers={"x-api-key": cfg["anthropic_api_key"],
                                       "anthropic-version": "2023-06-01"},
                              json={"model": cfg["anthropic_model"], "max_tokens": max_tokens,
                                    "system": system or "You are a world-class video director.",
                                    "messages": [{"role": "user", "content": prompt}]}, timeout=to)
            return r.json()["content"][0]["text"]
        if cfg["llm_provider"] == "ollama":
            import requests
            r = requests.post(cfg["ollama_url"] + "/api/chat",
                              json={"model": cfg["ollama_model"], "stream": False,
                                    "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": prompt}]},
                              timeout=int(cfg.get("ollama_timeout_s", 300)))
            return r.json()["message"]["content"]
    except Exception as e:
        log.warning("LLM unavailable (%s) -> using built-in director", e)
    return None


# ------------------------------------------------------------------ scripting
def _local_script(idea: str, target_s: int, fmt: str) -> list[dict]:
    """Heuristic pro writer used when no LLM key present."""
    wpv = FORMATS[fmt]["words_per_s"]
    n_scenes = max(3, min(14, int(target_s / 9)))
    words_total = int(target_s * wpv)
    topic = idea.strip().rstrip(".")
    hooks = [
        f"Here's something about {topic} almost nobody tells you.",
        f"What if everything you heard about {topic} was only half the story?",
        f"{topic.title()} — in the next few minutes this changes how you see it.",
    ]
    beats = [
        f"To understand {topic}, we first need the basics — where it started and why it matters at all.",
        f"The real turning point comes from data: experts measured it, and the numbers surprised everyone involved.",
        f"But there's a catch most coverage misses, and it quietly shapes everything people believe about {topic}.",
        f"Look at the ripple effects — industries, creators and everyday decisions now bend around this one idea.",
        f"Independent analysts keep reaching the same conclusion: the simple explanation was never the full picture.",
        f"So what does that mean for you? It means the smart move is to question the obvious answer and dig one layer deeper.",
        f"And that's the part worth remembering about {topic}: the story rewards curiosity, not headlines.",
    ]
    lines = [hooks[abs(hash(idea)) % len(hooks)]]
    i = 0
    while sum(len(l.split()) for l in lines) < words_total and i < n_scenes * 2:
        lines.append(beats[i % len(beats)] + (" Keep watching, because it gets better." if i == 1 else ""))
        i += 1
    lines.append("If this gave you a new angle, subscribe — next episode goes even deeper.")
    scenes = []
    per = max(1, len(lines) // n_scenes)
    for si in range(0, len(lines), per):
        chunk = " ".join(lines[si:si + per])
        scenes.append({"narration": chunk,
                       "visual_query": _query_for(chunk, topic),
                       "type": "broll"})
    return scenes[:max(3, n_scenes)]


def _query_for(text: str, topic: str) -> str:
    stop = set("the a an of and or to in for with on at it is was were are be been this that".split())
    words = [w.lower().strip(".,!?;:") for w in text.split() if w.lower().strip(".,!?;:") not in stop]
    top3 = " ".join(words[:3]) if words else topic
    return top3 or topic


def write_script(idea: str, target_s: int, fmt: str, style: str = "documentary") -> dict:
    wpv = FORMATS[fmt]["words_per_s"]
    llm_out = llm(
        f"Write a {style} voiceover script about: '{idea}'. Target spoken length ~{target_s}s "
        f"(about {int(target_s*wpv)} words). Split into 4-12 scenes. For EACH scene give: "
        "narration text (natural spoken style, no markdown), visual_query (2-4 stock-footage search "
        "words describing exactly what should be ON SCREEN while that line is spoken), optional stat "
        "(number+label if a figure helps), optional quote. Return STRICT JSON: "
        '{"title": "...", "scenes":[{"narration":"...","visual_query":"...","stat":{"value":0,"label":""}}]}',
        system="You are an expert documentary scriptwriter + video editor. You think like a motion-design lead."
    )
    if llm_out:
        m = re.search(r"\{.*\}", llm_out, re.S)
        if m:
            try:
                d = json.loads(m.group(0))
                if d.get("scenes"):
                    return d
            except Exception:
                pass
    return {"title": idea[:60], "scenes": _local_script(idea, target_s, fmt)}


# ------------------------------------------------------------------ pipeline
def generate_video(idea: str, *, fmt: str = "long", target_minutes: float | None = None,
                   caption_preset: str | None = None, voice: str | None = None,
                   tts_engine_name: str | None = None, music_path: str | None = None,
                   music_volume: float = 0.16, watermark: str = "",
                   progress=None, project_dir: str | None = None,
                   use_browser: bool | None = None, style: str = "documentary") -> dict:
    def say(pct, msg):
        log.info("[%.0f%%] %s", pct * 100, msg)
        if progress:
            progress(pct, msg)

    # resolve browser opt-in: explicit arg wins, else fall back to config flag
    if use_browser is None:
        use_browser = bool(config.CFG.get("browser_fallback_enabled", False))
    fmt_spec = FORMATS.get(fmt, FORMATS["long"])
    target_s = int((target_minutes or (0.55 if fmt == "short" else 3.0)) * 60)
    target_s = min(target_s, fmt_spec["max_s"])
    pid = uuid.uuid4().hex[:8]
    workdir = project_dir or os.path.join(config.PROJECTS_DIR, f"{pid}_{re.sub(r'[^a-z0-9]+','_',idea.lower()[:30])}")
    os.makedirs(workdir, exist_ok=True)

    # 1. script
    say(0.05, "Writing script…")
    script = write_script(idea, target_s, fmt, style)
    with open(os.path.join(workdir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)
    scenes = script["scenes"]

    # 2. narration per scene (auto-sync anchor)
    say(0.15, "Recording narration…")
    vo_files = []
    for i, sc in enumerate(scenes):
        mp3 = os.path.join(workdir, f"vo_{i:02d}.mp3")
        tsj = os.path.join(workdir, f"vo_{i:02d}.json")
        res = tts_engine.synthesize(sc["narration"], mp3, voice=voice,
                                    engine=tts_engine_name, word_timestamps_json=tsj)
        dur = media_duration(mp3) or 3.0
        # offset word stamps by cumulative start later; store raw here
        vo_files.append({"path": mp3, "dur": dur,
                         "words": json.load(open(tsj, encoding="utf-8")) if os.path.exists(tsj) else [],
                         "scene": sc})
        say(0.15 + 0.25 * (i + 1) / len(vo_files), f"Narration {i+1}/{len(vo_files)} ✓ ({res['engine']})")

    total_dur = sum(v["dur"] for v in vo_files)

    # 3. source footage synced to each scene's spoken duration
    say(0.42, "Sourcing b-roll (royalty-free)…")
    clips: list[Clip] = []
    cursor = 0.0
    all_words: list[dict] = []
    ci = 0
    for v in vo_files:
        sc = v["scene"]
        q = sc.get("visual_query") or _query_for(sc["narration"], idea)
        asset = None
        deadline = time.time() + float(config.CFG.get("provider_budget_s", 25))
        try:
            found = media_search.search_all(q, kind="video", per_provider=4)
            # rank candidates: right orientation first, then known duration fit
            ar = fmt_spec["w"] / fmt_spec["h"]
            def _rank(a):
                a_ar = (a.get("width") or 16) / (a.get("height") or 9) if a.get("width") else \
                       (16/9 if ar >= 1 else 9/16)
                orient_ok = abs(a_ar - ar) < 0.7
                dur_ok = (a.get("duration") or 99) >= v["dur"]
                return (orient_ok, dur_ok)
            found.sort(key=_rank, reverse=True)
            for cand in found[:3]:   # try up to 3 before giving up (fast fail)
                if time.time() > deadline:
                    break
                try:
                    local = media_search.fetch_asset(cand)
                    asset = cand
                    asset["_local"] = local
                    break
                except Exception as e:
                    log.info("asset download failed (%s): %s", cand.get("source"), e)
        except Exception as e:
            log.info("stock fetch failed for '%s': %s", q, e)
        if (not asset or "_local" not in asset) and use_browser \
                and config.CFG.get("browser_fallback_enabled", False) \
                and time.time() < deadline:
            # built-in browser fallback for REAL event footage
            try:
                from .browser import ForgeBrowser, quick_fetch_page, download_from_browser
                got = None
                if media_search.__dict__.get("_pw_ok"):
                    with ForgeBrowser(headless=True) as br:
                        br.goto("https://duckduckgo.com/?q=" + q.replace(" ", "+") + "&iax=images&ia=images")
                        imgs = br.image_search(q, 6)
                        if imgs:
                            got = download_from_browser(imgs[0]["url"], br.page.url)
                if got:
                    asset = {"kind": "image", "_local": got, "license": "web capture – verify reuse"}
            except Exception as e:
                log.info("browser fallback skipped: %s", e)
        if not asset or "_local" not in asset:
            # last resort: generated motion-graphic card so sync never breaks
            g = mg.stat_counter(workdir, value=len(sc["narration"]), label=q.title(),
                                W=fmt_spec["w"], H=fmt_spec["h"],
                                dur_s=max(3.0, v["dur"]), fps=fmt_spec and 30,
                                out=os.path.join(workdir, f"gen_{ci}.mov"))
            asset = {"kind": "generated", "_local": g, "license": "VidForge generated"}
        src = asset.get("_local")
        kind = "image" if asset.get("kind") == "image" else \
               "generated" if asset.get("kind") == "generated" else "video"
        c = Clip(id=f"c{ci}", kind=("generated" if kind == "generated" else kind), source=src,
                 in_s=0.0, out_s=v["dur"], transition=("fade" if ci == 0 else "cut"),
                 ken_burns="zoomin" if kind in ("image", "generated") else "",
                 meta={"license": asset.get("license", ""), "page": asset.get("page", "")})
        if kind == "generated":
            c.out_s = v["dur"]
        clips.append(c)

        # shift word timestamps onto global timeline
        for w in v["words"]:
            all_words.append({"text": w["text"],
                              "start_ms": w["start_ms"] + int(cursor * 1000),
                              "end_ms": w["end_ms"] + int(cursor * 1000)})
        cursor += v["dur"]
        ci += 1
        say(0.42 + 0.3 * ci / len(vo_files), f"Scene {ci}/{len(vo_files)} footage ready")

    # 4. captions synced to words
    preset = caption_preset or config.CFG.get("caption_default") or \
        (captions.DEFAULT_SHORT_PRESET if fmt == "short" else captions.DEFAULT_LONG_PRESET)
    say(0.75, "Burning animated captions…")
    ass = captions.render_ass(preset, fmt_spec["w"], fmt_spec["h"], all_words)
    with open(os.path.join(workdir, "captions.ass"), "w", encoding="utf-8") as f:
        f.write(ass)

    # 5. assemble timeline
    tl = Timeline(width=fmt_spec["w"], height=fmt_spec["h"], fps=30, crf=config.CFG["default_crf"],
                  clips=clips,
                  voiceover=[{"path": v["path"], "start_s": s, "words": []}
                             for v, s in zip(vo_files, [sum(x["dur"] for x in vo_files[:i]) for i in range(len(vo_files))])],
                  music=({"path": music_path, "volume": music_volume, "ducking": True} if music_path else None),
                  captions_preset=preset, captions_enabled=True,
                  watermark=watermark, progress_bar=(fmt == "short"),
                  title=script.get("title", idea)[:60],
                  chapters=[{"t_s": sum(v["dur"] for v in vo_files[:i]),
                             "title": (v["scene"].get("visual_query") or f"Scene {i+1}").title()}
                            for i, v in enumerate(vo_files) if i > 0])
    # NOTE: captions already carry global offsets; voiceovers placed sequentially
    out = os.path.join(workdir, "final.mp4")
    say(0.8, "Rendering final cut…")
    meta = render(tl, out, workdir, progress_cb=lambda p: say(0.8 + 0.2 * p, "Rendering…"))
    meta.update({"project_dir": workdir, "script": script, "format": fmt,
                 "duration_s": round(total_dur, 2), "caption_preset": preset})
    with open(os.path.join(workdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)
    say(1.0, "Done ✓")
    return meta


# ------------------------------------------------------------------ clipping
def clip_video(src: str, start_s: float, end_s: float, out: str, *,
               vertical: bool = False, reframe_center_x: float = 0.5,
               add_caption_strip: bool = False, burn_caption_preset: str | None = None,
               ass_file: str | None = None, speed: float = 1.0) -> str:
    """Short/long-form clipper: precise cuts, auto 9:16 reframe for shorts,
    optional caption burn & speed ramp."""
    from .render_engine import ffmpeg_bin
    exe = ffmpeg_bin()
    dur = end_s - start_s
    args = [exe, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start_s:.3f}", "-i", src, "-t", f"{dur:.3f}"]
    vf = []
    af = []
    if speed != 1.0:
        vf.append(f"setpts={1/speed:.4f}*PTS")
        sp = speed
        while sp > 2.0:
            af.append("atempo=2.0")
            sp /= 2.0
        while sp < 0.5:
            af.append("atempo=0.5")
            sp /= 0.5
        af.append(f"atempo={sp:.4f}")
    if vertical:
        # center-crop 9:16 from landscape then scale to 1080x1920
        vf.append("crop=ih*9/16:ih:(iw-ih*9/16)*%s:0,scale=1080:1920" % reframe_center_x)
    if ass_file:
        safe = ass_file.replace("\\", "/").replace(":", "\\:")
        vf.append(f"subtitles='{safe}'")
    if vf:
        args += ["-vf", ",".join(vf)]
    if af:
        args += ["-af", ",".join(af)]
    args += ["-c:v", "libx264", "-preset", "medium", "-crf", "19",
             "-c:a", "aac", "-movflags", "+faststart", out]
    import subprocess
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("clip failed: " + r.stderr[-800:])
    return out


def smart_clip_finder(src: str, *, want_s: float = 45.0, mode: str = "energy") -> list[dict]:
    """Find candidate highlight segments. 'energy' uses audio loudness via
    ffmpeg astats windows; returns [{start_s,end_s,score}]."""
    import subprocess
    from .render_engine import ffmpeg_bin, media_duration
    exe = ffmpeg_bin()
    dur = media_duration(src)
    win = 5.0
    scores = []
    t = 0.0
    while t < dur - 1:
        r = subprocess.run([exe, "-hide_banner", "-ss", f"{t}", "-t", f"{win}", "-i", src,
                            "-af", "astats=metadata=1:reset=1,volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True)
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
        rms = float(m.group(1)) if m else -91.0
        scores.append((t, rms))
        t += win
    ranked = sorted(scores, key=lambda x: -x[1])
    out, used = [], []
    for st, sc in ranked:
        if any(abs(st - u) < want_s for u in used):
            continue
        used.append(st)
        out.append({"start_s": round(st, 2), "end_s": round(min(dur, st + want_s), 2),
                    "score": round(sc, 1)})
        if len(out) >= 8:
            break
    return out
