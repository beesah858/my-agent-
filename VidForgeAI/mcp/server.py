"""VidForge AI - MCP server (Model Context Protocol, stdio transport).

Gives ANY MCP-capable LLM agent (Claude Desktop, Cursor, custom agents) FULL
control of the studio: research, script, TTS, stock search, built-in browser
capture, motion graphics, timeline editing and rendering.

Run standalone:  python mcp/server.py
Claude Desktop config example:
{
  "mcpServers": {
    "vidforge": { "command": "python", "args": [".../VidForgeAI/mcp/server.py"] }
  }
}
"""
from __future__ import annotations

import json
import os
import sys

# allow `python mcp/server.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (browser, captions, config, director, forge, media_search,
                  motion_graphics as mg, render_engine, tts_engine)

SERVER_INFO = {"name": "vidforge-studio", "version": config.VERSION}


def _j(**kw):
    return json.dumps(kw, default=str)


def _search_stock(query: str, kind: str = "video", per_provider: int = 8,
                  providers: list[str] | None = None) -> dict:
    """MCP-friendly wrapper so JSON-RPC results are self-describing for agents."""
    res = media_search.search_all(query, kind=kind, per_provider=per_provider,
                                  providers=providers)
    return {"query": query, "kind": kind, "count": len(res), "results": res[:40]}


TOOLS = {
    # ---- project / generation
    "generate_video": dict(
        fn=lambda idea, format="long", target_minutes=None, caption_preset=None,
             voice=None, music_path=None, style="documentary", use_browser=None:
            director.generate_video(idea, fmt=format, target_minutes=target_minutes,
                                    caption_preset=caption_preset, voice=voice,
                                    music_path=music_path, style=style,
                                    use_browser=use_browser),
        desc="FULL auto pipeline: idea -> researched script -> synced narration+footage -> captions -> rendered final.mp4 + editable project.json. format: short|long; use_browser=true to allow built-in browser real-footage capture (requires browser_fallback_enabled in config)"),
    "forge_create": dict(
        fn=lambda idea, fmt="short", **kw: forge.forge_create(idea, fmt=fmt, **kw),
        desc="⚡ FORGE STUDIO — full-control AI video builder. Args: idea; fmt short|long; "
             "target_minutes; style; voice/rate/pitch; caption_preset (any of 384 ids); "
             "music_path & music_volume; visual_mode auto|stock|hyperframe|mixed|image; "
             "script_text (user-pasted pro script with ## Scene/VO:/Visual: cues — bypasses AI writer); "
             "hook & cta lines; transitions cut|fade|slide|wipe|glitch; ken_burns; lufs; chapters; "
             "progress_bar; watermark; fps; crf; project_dir. Returns final.mp4 path + meta."),
    "forge_import_script": dict(
        fn=lambda text, idea="", fmt="long": {"title": forge.script_to_scenes(text, idea=idea, fmt=fmt)[0],
                                              "scenes": forge.script_to_scenes(text, idea=idea, fmt=fmt)[1]},
        desc="Convert a plain-text/markdown script into VidForge scenes (no rendering)."),
    "forge_status": dict(fn=forge.forge_status,
                         desc="Capability snapshot: remotion_ready, providers, caption presets, LLM."),
    "write_script": dict(fn=director.write_script,
                         desc="Write scene-by-scene narration script with per-scene visual queries"),
    # ---- speech
    "synthesize_speech": dict(
        fn=lambda text, out_mp3, voice=None, engine=None:
            tts_engine.synthesize(text, out_mp3, voice=voice, engine=engine,
                                  word_timestamps_json=out_mp3 + ".words.json"),
        desc="TTS with hardened Edge-TTS + offline fallback; returns word timestamps for sync"),
    "list_voices": dict(fn=tts_engine.list_edge_voices, desc="List all Edge-TTS voices"),
    # ---- media
    "search_stock_media": dict(
        fn=_search_stock,
        desc="Search Pexels/Pixabay/Unsplash/Coverr/Mixkit/Archive.org/Wikimedia/NASA royalty-free footage & images; returns {query, kind, count, results:[{url,kind,source,license,duration,width,height,page}]}"),
    "download_asset": dict(fn=media_search.fetch_asset,
                           desc="Download a found asset dict to a local cached file"),
    # ---- built-in browser (real event footage)
    "browser_open": dict(fn=lambda url: browser.ForgeBrowser().goto(url) if False else _browser_open(url),
                         desc="Open URL in VidForge's own headless browser, return title + sniffed media list"),
    "browser_download_media": dict(fn=lambda url, referer: browser.download_from_browser(url, referer),
                                   desc="Download a media URL found via browser_open into project cache"),
    # ---- motion graphics
    "make_lower_third": dict(fn=mg.lower_third, desc="Animated lower-third .mov overlay (transparent)"),
    "make_stat_counter": dict(fn=mg.stat_counter, desc="Animated big-number stat .mov overlay"),
    "make_title_reveal": dict(fn=mg.title_reveal, desc="Kinetic title reveal .mov overlay"),
    "make_chart_bars": dict(fn=mg.chart_bars, desc="Animated bar chart .mov overlay"),
    "make_quote_card": dict(fn=mg.quote_card, desc="Animated quote card overlay"),
    "make_subscribe_bumper": dict(fn=mg.subscribe_bumper, desc="YouTube subscribe bumper overlay"),
    # ---- captions
    "list_caption_presets": dict(fn=lambda family=None: [
        {"id": p.id, "name": p.name, "family": p.family}
        for p in captions.LIBRARY if not family or p.family == family],
        desc="216 CapCut-style animated caption presets"),
    "preview_caption_preset": dict(fn=captions.preview_png,
                                   desc="Render PNG preview of a caption preset"),
    "create_custom_caption": dict(
        fn=lambda id, name, font="Arial", size_pct=6.0, palette="yellow_pop",
             position="bottom", anim="pop", bold=True, border_px=3:
            captions.save_custom_preset(captions.CaptionPreset(
                id=id, name=name, family="Custom", font=font, size_pct=size_pct,
                palette=palette, position=position, bold=bold, italic=False,
                border_px=border_px, shadow_px=0, anim=anim, per_word=(anim != "minimal"))),
        desc="Create a NEW animated caption template (saved permanently)"),
    # ---- editing primitives
    "clip_video": dict(fn=director.clip_video,
                       desc="Cut a short/long clip; vertical=True reframes to 9:16 for Shorts; optional speed & caption burn"),
    "smart_clip_finder": dict(fn=director.smart_clip_finder,
                               desc="Detect high-energy highlight segments worth clipping from a long video"),
    "render_timeline": dict(fn=lambda project_json, out_mp4, workdir:
                            _render_from_project(project_json, out_mp4, workdir),
                            desc="Render an edited project.json timeline (after user/agent edits) to MP4"),
    "load_project": dict(fn=lambda path: json.load(open(path, encoding="utf-8")),
                         desc="Read a VidForge editable project.json timeline"),
    # ---- config
    "set_config": dict(fn=lambda key, value: _set_cfg(key, value),
                       desc="Set API keys / voices / models (pexels_api_key, openai_api_key, tts_voice...)"),
    "get_status": dict(fn=lambda: {"config_keys": list(config.CFG), "projects":
                          os.listdir(config.PROJECTS_DIR)},
                       desc="App status"),
}


def _browser_open(url: str):
    try:
        with browser.ForgeBrowser(headless=True) as br:
            title = br.goto(url)
            return {"title": title, "media": br.sniff_media()[:30]}
    except Exception:
        return browser.quick_fetch_page(url)


def _render_from_project(proj_path: str, out_mp4: str, workdir: str):
    proj = json.load(open(proj_path, encoding="utf-8"))
    tl = render_engine.Timeline(
        width=proj["canvas"]["w"], height=proj["canvas"]["h"],
        fps=proj["canvas"]["fps"], crf=proj["canvas"].get("crf", 19),
        clips=[render_engine.Clip(**c) for c in proj["clips"]],
        voiceover=proj["voiceover"], music=proj.get("music"),
        captions_preset=proj["captions"]["preset"],
        captions_enabled=proj["captions"]["enabled"],
        watermark=proj.get("watermark", ""), title=proj.get("title", ""),
        chapters=proj.get("chapters", []))
    words = [w for ws in proj.get("word_timestamps", []) for w in ws]
    if words and tl.captions_enabled:
        ass = captions.render_ass(tl.captions_preset, tl.width, tl.height, words)
        with open(os.path.join(workdir, "captions.ass"), "w", encoding="utf-8") as f:
            f.write(ass)
    return render_engine.render(tl, out_mp4, workdir)


def _set_cfg(k, v):
    config.CFG[k] = v
    config.save_config(config.CFG)
    return {"ok": True, k: v}


# ------------------------------------------------------------------ JSON-RPC loop
def _result(rid, res):
    return {"jsonrpc": "2.0", "id": rid, "result": res}


def handle(req: dict):
    method, rid = req.get("method"), req.get("id")
    params = req.get("params") or {}
    if method == "initialize":
        return _result(rid, {"protocolVersion": "2024-11-05",
                             "capabilities": {"tools": {}},
                             "serverInfo": SERVER_INFO})
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "tools/list":
        return _result(rid, {"tools": [
            {"name": n, "description": t["desc"],
             "inputSchema": {"type": "object"}} for n, t in TOOLS.items()]})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            return _result(rid, {"isError": True,
                                 "content": [{"type": "text", "text": f"unknown tool {name}"}]})
        try:
            out = tool["fn"](**args)
            return _result(rid, {"content": [{"type": "text",
                                              "text": json.dumps(out, default=str)[:12000]}]})
        except Exception as e:
            return _result(rid, {"isError": True,
                                 "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}]})
    if method == "ping":
        return _result(rid, {})
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"method {method} not found"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
