"""VidForge AI — command-line studio (also the .exe entry point).

Examples:
  python vidforge.py generate "5 deep ocean secrets" --short -m 0.5
  python vidforge.py generate "history of Rome" --long -m 8 --preset karaoke-fire-144
  python vidforge.py tts "hello world" -o hello.mp3
  python vidforge.py search "sunset beach" --kind video
  python vidforge.py clip input.mp4 --start 12 --end 72 --vertical -o highlight.mp4
  python vidforge.py find-highlights input.mp4
  python vidforge.py render project.json -o final.mp4
  python vidforge.py gui
  python vidforge.py mcp
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(prog="vidforge", description="VidForge AI — local AI video factory")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="idea -> full ready-to-publish video")
    g.add_argument("idea")
    g.add_argument("--short", action="store_true"); g.add_argument("--long", action="store_true")
    g.add_argument("-m", "--minutes", type=float, default=None)
    g.add_argument("--voice", default=None); g.add_argument("--preset", default=None)
    g.add_argument("--music", default=None); g.add_argument("--style", default="documentary")
    g.add_argument("--no-browser", action="store_true")

    t = sub.add_parser("tts", help="speech with hardened Edge-TTS + offline fallback")
    t.add_argument("text"); t.add_argument("-o", "--out", default="speech.mp3")
    t.add_argument("--voice", default=None); t.add_argument("--engine", default=None)

    s = sub.add_parser("search", help="royalty-free stock search (Pexels/Pixabay/Unsplash/Coverr/Mixkit/Archive)")
    s.add_argument("query"); s.add_argument("--kind", default="video")
    s.add_argument("--provider", default=None)

    d = sub.add_parser("download", help="download a found asset URL into cache")
    d.add_argument("url"); d.add_argument("--kind", default="video")

    c = sub.add_parser("clip", help="cut short/long clips, optional 9:16 reframe & speed")
    c.add_argument("src"); c.add_argument("--start", type=float); c.add_argument("--end", type=float)
    c.add_argument("--vertical", action="store_true"); c.add_argument("--speed", type=float, default=1.0)
    c.add_argument("-o", "--out", default="clip.mp4")

    fh = sub.add_parser("find-highlights", help="auto-detect best moments to clip from a long video")
    fh.add_argument("src"); fh.add_argument("--want", type=float, default=45.0)

    r = sub.add_parser("render", help="re-render an edited project.json timeline")
    r.add_argument("project"); r.add_argument("-o", "--out", default="final.mp4")

    p = sub.add_parser("presets", help="list caption presets"); p.add_argument("--family", default=None)

    sub.add_parser("gui", help="open the VidForge Studio window")
    sub.add_parser("mcp", help="run the MCP agent server on stdio")

    a = ap.parse_args()

    if a.cmd == "generate":
        from core import director
        fmt = "short" if a.short else "long"
        meta = director.generate_video(a.idea, fmt=fmt, target_minutes=a.minutes,
                                       voice=a.voice, caption_preset=a.preset,
                                       music_path=a.music, style=a.style,
                                       use_browser=(False if a.no_browser else None),
                                       progress=lambda pct, msg: print(f"[{pct*100:3.0f}%] {msg}"))
        print(json.dumps(meta, indent=2, default=str))
    elif a.cmd == "tts":
        from core import tts_engine
        res = tts_engine.synthesize(a.text, a.out, voice=a.voice, engine=a.engine,
                                    word_timestamps_json=a.out + ".words.json")
        print(f"OK via {res['engine']} → {a.out} ({len(res.get('words', []))} word stamps)")
    elif a.cmd == "search":
        from core import media_search
        provs = [a.provider] if a.provider else None
        for x in media_search.search_all(a.query, kind=a.kind, providers=provs):
            print(f"- [{x['source']}] {x['kind']} :: {x.get('credit','')} :: {x['url'][:90]}")
    elif a.cmd == "download":
        from core import media_search
        print(media_search.download(a.url, ext=".mp4" if a.kind == "video" else ".jpg"))
    elif a.cmd == "clip":
        from core import director
        print(director.clip_video(a.src, a.start, a.end, a.out, vertical=a.vertical, speed=a.speed))
    elif a.cmd == "find-highlights":
        from core import director
        for seg in director.smart_clip_finder(a.src, want_s=a.want):
            print(seg)
    elif a.cmd == "render":
        from mcp.server import _render_from_project
        print(_render_from_project(a.project, a.out, os.path.dirname(os.path.abspath(a.project))))
    elif a.cmd == "presets":
        from core import captions
        fams = sorted({pp.family for pp in captions.LIBRARY})
        if a.family:
            for pp in captions.LIBRARY:
                if pp.family.lower() == a.family.lower():
                    print(f"{pp.id:32s} {pp.name}")
        else:
            print(f"{len(captions.LIBRARY)} presets in families:")
            print(", ".join(fams))
    elif a.cmd == "gui":
        from ui.app import main as gui_main
        gui_main()
    elif a.cmd == "mcp":
        from mcp.server import main as mcp_main
        mcp_main()


if __name__ == "__main__":
    main()
