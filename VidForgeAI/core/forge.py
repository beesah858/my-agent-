"""VidForge AI — Forge Studio engine (v2.3).

The one-stop "Create" brain behind the 🧪 Forge Studio tab, the `forge` CLI
command and the MCP `forge_create` tool. It turns an idea (or a hand-written /
LLM script) into a ready-to-publish SHORT (9:16) or LONG (16:9) video with
per-scene control over everything an editor cares about:

  • narration per scene   → hardened Edge-TTS (+ local pyttsx3/espeak fallback),
                            rate/pitch/voice selectable, word timestamps kept
  • visual source mode    → stock | hyperframe (Remotion data dashboards) |
                            mixed (stock + transparent HUD overlay) | image | auto
  • animated captions     → any of the 384 CapCut-style presets, burned in
  • music bed             → auto-ducked under voiceover (-14 LUFS polish)
  • audio↔video sync      → each scene's footage length = its spoken length,
                            frame-for-frame ("jo bola wahi dikhe")

Also ships `script_to_scenes(text)` which converts a plain-text / markdown
script (## Scene N blocks or bare paragraphs) into director scenes using the
configured LLM when available, else a smart local splitter — so users can paste
their own pro script and still get full automatic assembly.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid

from . import captions, config, director, hyperframe, media_search, tts_engine
from .render_engine import Clip, Timeline, media_duration, render

log = logging.getLogger("vidforge.forge")

VISUAL_MODES = ["auto", "stock", "hyperframe", "mixed", "image"]


# ------------------------------------------------------------------ script import
def _split_plain_script(text: str) -> list[dict]:
    """Parse '## Scene 1 ...' blocks or blank-line paragraphs into scenes."""
    blocks: list[str] = []
    m = re.split(r"(?m)^\s*(?:#{1,3}\s*)?(?:scene|part|segment)\s*\d+\s*:?\s*$",
                 text, flags=re.I)
    if len(m) > 1:
        blocks = [b.strip() for b in m if b and b.strip()]
    if not blocks:
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    scenes = []
    for b in blocks[:14]:
        # first line often a VISUAL cue if prefixed
        lines = [l.strip() for l in b.splitlines() if l.strip()]
        narr_parts, vis = [], ""
        for l in lines:
            lm = re.match(r"^(?:visual|b-?roll|footage|on[- ]screen)\s*[:\-]\s*(.+)", l, re.I)
            if lm:
                vis = lm.group(1)[:60]
            else:
                narr_parts.append(re.sub(r"^VO\s*[:\-]\s*", "", l))
        narr = " ".join(narr_parts).strip()
        if not narr:
            continue
        words = re.findall(r"[A-Za-z][\w'-]{2,}", narr)
        scenes.append({"narration": narr,
                       "visual_query": vis or " ".join(words[:3])})
    return scenes


def script_to_scenes(text: str, *, idea: str = "", fmt: str = "long",
                     use_llm: bool = True) -> tuple[str, list[dict]]:
    """Return (title, scenes) from user-pasted script text."""
    title = ""
    first = text.strip().splitlines()[0] if text.strip() else "Untitled"
    tm = re.match(r"^\s*(?:#\s*|title\s*[:\-]\s*)(.+)", first, re.I)
    body = text
    if tm:
        title, body = tm.group(1).strip(), "\n".join(text.strip().splitlines()[1:])
    if not title:
        title = (idea or first)[:60]
    if use_llm and config.CFG.get("llm_provider", "none") != "none" \
            and (config.CFG.get("openai_api_key") or config.CFG.get("anthropic_api_key")
                 or config.CFG.get("openai_base_url")
                 or config.CFG.get("llm_provider") == "ollama"):
        out = director.llm(
            "Split this voiceover script into scenes. Return STRICT JSON "
            '{"scenes":[{"narration":"...","visual_query":"2-4 footage search words"}]}:\n\n'
            + body[:6000])
        if out:
            m = re.search(r"\{.*\}", out, re.S)
            try:
                d = json.loads(m.group(0)) if m else {}
                if d.get("scenes"):
                    return title, d["scenes"][:14]
            except Exception:
                pass
    return title, _split_plain_script(body)


# ------------------------------------------------------------------ asset helpers
def _try_stock(q: str, deadline: float, want_dur: float, ar: float) -> dict | None:
    try:
        found = media_search.search_all(q, kind="video", per_provider=4)
        found.sort(key=lambda a: ((a.get("duration") or 99) >= want_dur), reverse=True)
        for cand in found[:3]:
            if time.time() > deadline:
                return None
            try:
                local = media_search.fetch_asset(cand)
                cand["_local"] = local
                cand["kind"] = "video"
                return cand
            except Exception:
                continue
    except Exception as e:
        log.info("stock search failed '%s': %s", q, e)
    return None


def _try_image(q: str, deadline: float) -> dict | None:
    try:
        found = media_search.search_all(q, kind="image", per_provider=6)
        for cand in found[:3]:
            if time.time() > deadline:
                return None
            try:
                cand["_local"] = media_search.fetch_asset(cand)
                cand["kind"] = "image"
                return cand
            except Exception:
                continue
    except Exception:
        pass
    return None


def _hf_items_for(scene: dict, idx: int) -> tuple[str, list[dict], str]:
    """Build HyperFrame tiles from a scene (stats/keywords auto-extracted)."""
    narr = scene.get("narration", "")
    nums = [float(n.replace(",", "")) for n in re.findall(r"\b\d[\d,]*\.?\d*\b", narr)]
    stat = scene.get("stat") or {}
    title = (scene.get("visual_query") or f"Fact {idx+1}").title()[:44]
    items: list[dict] = []
    if stat.get("value") is not None:
        items.append(hyperframe._tile_stat(stat.get("label", title), stat["value"]))
    if len(nums) >= 2:
        items += [hyperframe._tile_stat(f"{title[:18]} #{i+1}", n)
                  for i, n in enumerate(nums[:4])]
        layout = "statwall"
    elif nums:
        items.append(hyperframe._tile_stat(title[:18], nums[0]))
        items.append(hyperframe._tile_text(narr[:120]))
        layout = "hero"
    else:
        kws = [w.strip().title() for w in re.findall(r"[A-Za-z][A-Za-z .&/-]{3,32}", narr)][:4]
        items.append(hyperframe._tile_text(narr[:150], big=True))
        items += [hyperframe._tile_chip(k) for k in kws[:3]]
        layout = "grid"
    if not items:
        items = [hyperframe._tile_text(narr[:160] or title, big=True)]
        layout = "fullbleed"
    return title, items, layout


# ------------------------------------------------------------------ main entry
def forge_create(idea: str, *, fmt: str = "short", target_minutes: float | None = None,
                 style: str = "documentary", voice: str | None = None,
                 rate: str | None = None, pitch: str | None = None,
                 caption_preset: str | None = None, music_path: str | None = None,
                 music_volume: float = 0.16, visual_mode: str = "auto",
                 per_scene: list[dict] | None = None, script_text: str | None = None,
                 hook: str = "", cta: str = "", transitions: str = "fade",
                 ken_burns: bool = True, lufs: bool = True, progress_bar: bool | None = None,
                 chapters: bool = True, watermark: str = "", crf: int | None = None,
                 fps: int = 30, use_browser: bool | None = None,
                 progress=None, project_dir: str | None = None) -> dict:
    """Full controllable pipeline. Returns meta dict like director.generate_video."""
    def say(pct, msg):
        log.info("[%.0f%%] %s", pct * 100, msg)
        if progress:
            progress(pct, msg)

    fspec = director.FORMATS.get(fmt, director.FORMATS["long"])
    W, H = fspec["w"], fspec["h"]
    ar = W / H
    budget = float(config.CFG.get("provider_budget_s", 25))
    if use_browser is None:
        use_browser = bool(config.CFG.get("browser_fallback_enabled", False))

    # ---------- 1. scenes: user script > per_scene overrides > AI writer
    title = idea[:60]
    if script_text and script_text.strip():
        say(0.04, "Importing your script…")
        title, scenes = script_to_scenes(script_text, idea=idea, fmt=fmt)
    else:
        say(0.05, "Writing script…")
        target_s = int((target_minutes or (0.55 if fmt == "short" else 3.0)) * 60)
        target_s = min(target_s, fspec["max_s"])
        sc = director.write_script(idea, target_s, fmt, style)
        title, scenes = sc.get("title", title), sc["scenes"]
    if hook.strip():
        scenes.insert(0, {"narration": hook.strip(), "visual_query": idea[:30]})
    if cta.strip():
        scenes.append({"narration": cta.strip(), "visual_query": "subscribe community"})
    if per_scene:
        for i, ov in enumerate(per_scene):
            if i < len(scenes) and isinstance(ov, dict):
                scenes[i].update({k: v for k, v in ov.items() if v not in (None, "")})
    workdir = project_dir or os.path.join(
        config.PROJECTS_DIR,
        f"{uuid.uuid4().hex[:8]}_{re.sub(r'[^a-z0-9]+', '_', (idea or title).lower())[:30]}")
    os.makedirs(workdir, exist_ok=True)
    with open(os.path.join(workdir, "script.json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "scenes": scenes}, f, indent=2, ensure_ascii=False)

    # ---------- 2. narration (word-stamped, per-scene rate/pitch override ok)
    say(0.14, "Recording narration…")
    vo_files = []
    for i, scn in enumerate(scenes):
        mp3 = os.path.join(workdir, f"vo_{i:02d}.mp3")
        tsj = mp3 + ".json"
        res = tts_engine.synthesize(scn["narration"], mp3,
                                    voice=(scn.get("voice") or voice),
                                    rate=scn.get("rate") or rate,
                                    pitch=scn.get("pitch") or pitch,
                                    word_timestamps_json=tsj)
        dur = media_duration(mp3) or 3.0
        vo_files.append({"path": mp3, "dur": dur, "scene": scn,
                         "words": json.load(open(tsj, encoding="utf-8")) if os.path.exists(tsj) else [],
                         "engine": res["engine"]})
        say(0.14 + 0.24 * (i + 1) / len(scenes),
            f"Narration {i+1}/{len(scenes)} ✓ ({res['engine']})")

    # ---------- 3. visuals per scene, duration-locked to VO (perfect sync)
    say(0.40, f"Sourcing visuals (mode: {visual_mode})…")
    clips: list[Clip] = []
    all_words: list[dict] = []
    cursor = 0.0
    for i, v in enumerate(vo_files):
        scn = v["scene"]
        q = scn.get("visual_query") or f"topic {idea}".strip()
        mode = (scn.get("visual_mode") or visual_mode or "auto").lower()
        deadline = time.time() + budget
        asset = None
        hf_out = None
        if mode in ("stock", "auto", "mixed", "image"):
            asset = (_try_stock(q, deadline, v["dur"], ar) if mode != "image"
                     else _try_image(q, deadline))
            if not asset and mode in ("auto", "image"):
                asset = _try_image(q, deadline) if mode == "auto" else None
        if mode in ("hyperframe", "mixed") or (mode == "auto" and not asset):
            t, items, layout = _hf_items_for(scn, i)
            hf_out = hyperframe.hyper_frame(workdir, t, items, layout=layout,
                                            dur_s=max(3.0, v["dur"]), W=W, H=H, fps=fps,
                                            out=os.path.join(workdir, f"hf_{i:02d}.mp4"))
        hud_src = None
        if mode == "mixed" and asset and "_local" in asset:
            # transparent HyperFrame HUD composited over the stock footage
            try:
                from . import remotion_bridge as _rm
                if _rm.available():
                    t2, items2, _ = _hf_items_for(scn, i)
                    hud_src = _rm.render_clip(
                        "HyperFrame",
                        hyperframe.build_props(t2, items2, layout="hero"),
                        os.path.join(workdir, f"hud_{i:02d}.webm"),
                        width=W, height=H, fps=fps,
                        duration_in_frames=int(max(3.0, v["dur"]) * fps),
                        transparent=True)
            except Exception as e:
                log.info("mixed HUD skipped (remotion unavailable): %s", e)
        if asset and "_local" in asset:
            src, kind = asset["_local"], asset.get("kind", "video")
            lic = asset.get("license", "")
        elif hf_out:
            src, kind, lic = hf_out, "generated", "HyperFrame motion graphic"
        elif use_browser:
            got = None
            try:
                from .browser import download_from_browser, quick_fetch_page
                page = quick_fetch_page("https://duckduckgo.com/?q=" +
                                        q.replace(" ", "+"))
                if page and page.get("images"):
                    got = download_from_browser(page["images"][0]["url"], page["url"])
            except Exception as e:
                log.info("browser fallback skipped: %s", e)
            if got:
                src, kind, lic = got, "image", "web capture – verify reuse"
            else:
                raise RuntimeError(f"scene {i+1}: no footage for '{q}' "
                                   "(enable browser fallback or add API keys)")
        else:
            raise RuntimeError(f"scene {i+1}: no footage for '{q}' "
                               "(add Pexels/Pixabay keys in Settings or enable browser)")
        tr = {"cut": "cut", "fade": "fade", "slide": "slideleft",
              "wipe": "wipe", "glitch": "glitch"}.get(transitions, "cut")
        c = Clip(id=f"c{i}", kind=("generated" if kind == "generated" else kind),
                 source=src, in_s=0.0, out_s=v["dur"],
                 transition=("cut" if i == 0 else tr),
                 ken_burns=("zoomin" if (ken_burns and kind in ("image", "generated")) else ""),
                 meta={"license": lic, "query": q})
        clips.append(c)
        if hud_src:
            clips.append(Clip(id=f"h{i}", kind="generated", source=hud_src,
                              in_s=0.0, out_s=v["dur"], layer=1,
                              pip={"w_pct": 100, "x_pct": 0, "y_pct": 0},
                              meta={"license": "HyperFrame HUD overlay"}))
        for w in v["words"]:
            all_words.append({"text": w["text"],
                              "start_ms": w["start_ms"] + int(cursor * 1000),
                              "end_ms": w["end_ms"] + int(cursor * 1000)})
        cursor += v["dur"]
        say(0.40 + 0.30 * (i + 1) / len(vo_files),
            f"Scene {i+1}/{len(vo_files)} visual locked to speech ✓")

    # ---------- 4. captions
    preset = caption_preset or (captions.DEFAULT_SHORT_PRESET if fmt == "short"
                                else captions.DEFAULT_LONG_PRESET)
    say(0.72, "Burning animated captions…")
    ass = captions.render_ass(preset, W, H, all_words)
    with open(os.path.join(workdir, "captions.ass"), "w", encoding="utf-8") as f:
        f.write(ass)
    srt = os.path.join(workdir, "captions.srt")
    from .render_engine import write_srt
    write_srt(all_words, srt)

    # ---------- 5. assemble + render
    tl = Timeline(width=W, height=H, fps=fps,
                  crf=crf or config.CFG["default_crf"], clips=clips,
                  voiceover=[{"path": v["path"], "start_s": s, "words": []}
                             for v, s in zip(vo_files,
                                             [sum(x["dur"] for x in vo_files[:k])
                                              for k in range(len(vo_files))])],
                  music=({"path": music_path, "volume": music_volume, "ducking": True}
                         if music_path else None),
                  captions_preset=preset, captions_enabled=bool(all_words),
                  watermark=watermark,
                  progress_bar=(fmt == "short") if progress_bar is None else progress_bar,
                  lufs_normalize=lufs, title=title,
                  chapters=([{"t_s": sum(v["dur"] for v in vo_files[:k]),
                              "title": (v["scene"].get("visual_query") or f"Scene {k+1}").title()}
                             for k, v in enumerate(vo_files) if k > 0] if chapters else []))
    out = os.path.join(workdir, "final.mp4")
    say(0.78, "Rendering final cut…")
    meta = render(tl, out, workdir,
                  progress_cb=lambda p: say(0.78 + 0.22 * p, "Rendering…"))
    meta.update({"project_dir": workdir, "format": fmt, "visual_mode": visual_mode,
                 "duration_s": round(cursor, 2), "caption_preset": preset,
                 "title": title, "script": {"title": title, "scenes": scenes},
                 "captions_srt": srt})
    with open(os.path.join(workdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)
    say(1.0, "Done ✓")
    return meta


def forge_status() -> dict:
    """Quick capability snapshot for the UI header."""
    from . import remotion_bridge
    cfg = config.CFG
    return {
        "remotion_ready": remotion_bridge.available(),
        "edge_tts": True,
        "providers_enabled": len(cfg.get("enabled_providers") or media_search.PROVIDERS),
        "caption_presets": len(captions.LIBRARY),
        "browser_enabled": bool(cfg.get("browser_fallback_enabled", False)),
        "llm": cfg.get("llm_provider", "none"),
    }
