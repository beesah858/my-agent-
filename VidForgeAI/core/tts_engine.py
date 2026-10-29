"""VidForge AI - Speech engine with HARDENED Edge-TTS + offline fallbacks.

Fixes the classic 'edge tts not working' problems:
  * stale/blocked token handshake  -> retry loop w/ backoff + voice rotation
  * proxy / SSL issues             -> per-attempt diagnostics in log
  * fully offline machines         -> pyttsx3 (SAPI5/Linux espeak) fallback
Also returns word-level timestamps for karaoke captions & audio/video sync.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time

from . import config

log = logging.getLogger("vidforge.tts")

# popular multilingual voices tried when a specific voice keeps failing
_FALLBACK_VOICES = [
    "en-US-AriaNeural", "en-US-GuyNeural", "en-GB-SoniaNeural",
    "en-AU-NatashaNeural", "en-US-JennyNeural", "ur-PK-IraNeural",
    "hi-IN-SwaraNeural", "ar-SA-ZariyahNeural",
]


def list_edge_voices() -> list[dict]:
    try:
        voices = asyncio.run(_edge_list())
        return voices
    except Exception as e:
        log.warning("voice list failed: %s", e)
        return []


async def _edge_list():
    import edge_tts
    return await edge_tts.list_voices()


async def _edge_synth_once(text: str, out_mp3: str, voice: str,
                           rate: str, pitch: str, word_ts_json: str | None):
    """One attempt at Edge-TTS synthesis, capturing WordBoundary events.
    edge-tts>=7 defaults to SentenceBoundary -> we explicitly request WordBoundary."""
    import edge_tts
    com = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch,
                               boundary="WordBoundary")
    words = []
    buf = b""
    async for chunk in com.stream():
        if chunk["type"] == "audio":
            buf += chunk["data"]
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            words.append({
                "text": chunk.get("text", ""),
                "start_ms": int(chunk.get("offset", 0) / 10000),   # 100ns -> ms
                "end_ms": int((chunk.get("offset", 0) + chunk.get("duration", 0)) / 10000),
            })
    if not buf:
        raise RuntimeError("edge-tts returned no audio bytes")
    with open(out_mp3, "wb") as f:
        f.write(buf)
    if not words:  # some voices never emit boundaries -> estimate from duration
        dur = _probe_duration(out_mp3)
        words = _estimate_words_from_text(text, dur)
    if word_ts_json and words:
        with open(word_ts_json, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False)
    return len(buf), words


def synthesize(text: str, out_mp3: str, *, voice: str | None = None,
               rate: str | None = None, pitch: str | None = None,
               word_timestamps_json: str | None = None,
               engine: str | None = None) -> dict:
    """Synthesize speech. Returns {'engine':..., 'words':[...], 'path':...}."""
    cfg = config.CFG
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise ValueError("empty text for TTS")
    engine = (engine or cfg.get("tts_engine", "edge")).lower()
    voice = voice or cfg.get("tts_voice", "en-US-AriaNeural")
    rate = rate or cfg.get("tts_rate", "+8%")
    pitch = pitch or cfg.get("tts_pitch", "+0Hz")

    errors = []
    if engine == "edge":
        ok = False
        # attempt order: requested voice first, then popular fallbacks
        for attempt, v in enumerate([voice] + [x for x in _FALLBACK_VOICES if x != voice][:4]):
            for retry in range(2):
                try:
                    n, words = asyncio.run(_edge_synth_once(
                        text, out_mp3, v, rate, pitch, word_timestamps_json))
                    if n > 500:
                        log.info("edge-tts OK voice=%s bytes=%d words=%d", v, n, len(words))
                        return {"engine": "edge", "voice": v, "path": out_mp3,
                                "words": words}
                    raise RuntimeError("tiny payload (token blocked?)")
                except Exception as e:
                    errors.append(f"edge[{v}]#{retry}: {e}")
                    log.warning(errors[-1])
                    time.sleep(1.2 * (retry + 1))
        # fall through to offline engines automatically
        log.warning("edge-tts exhausted (%d errors) -> falling back to local TTS", len(errors))

    if engine in ("pyttsx3", "espeak", "edge"):  # offline chain
        try:
            import pyttsx3
            eng = pyttsx3.init()
            vs = cfg.get("pyttsx3_voice")
            if vs:
                for vv in eng.getProperty("voices"):
                    if vs.lower() in (vv.name or "").lower():
                        eng.setProperty("voice", vv.id)
            eng.setProperty("rate", 175)
            eng.save_to_file(text, out_mp3)
            eng.runAndWait()
            if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 500:
                return {"engine": "pyttsx3", "path": out_mp3, "words": []}
        except Exception as e:
            errors.append(f"pyttsx3: {e}")
            log.warning(str(e))
        # last resort: espeak-ng raw wav (fully offline)
        if shutil.which("espeak-ng") or shutil.which("espeak"):
            binp = shutil.which("espeak-ng") or shutil.which("espeak")
            wav = out_mp3 + ".wav"
            try:
                subprocess.run([binp, "-w", wav, text], check=True, capture_output=True)
                subprocess.run([cfg.get("ffmpeg_path", "ffmpeg"), "-y", "-i", wav,
                                "-b:a", "128k", out_mp3], check=True, capture_output=True)
                words = _estimate_words_from_text(text, _probe_duration(out_mp3))
                if word_timestamps_json:
                    with open(word_timestamps_json, "w", encoding="utf-8") as f:
                        json.dump(words, f, ensure_ascii=False)
                return {"engine": "espeak", "path": out_mp3, "words": words}
            except Exception as e:
                errors.append(f"espeak: {e}")

    raise RuntimeError("All TTS engines failed:\n" + "\n".join(errors[-6:]))


def _probe_duration(path: str) -> float:
    try:
        out = subprocess.check_output(
            [config.CFG.get("ffprobe_path", "ffprobe"), "-v", "error",
             "-show_entries", "format=duration", "-of", "json", path], text=True)
        return float(json.loads(out)["format"]["duration"])
    except Exception:
        return max(1.0, len(path) * 0.0)


def _estimate_words_from_text(text: str, dur: float) -> list[dict]:
    """Uniformly spread word timestamps when engine gives none (offline mode)."""
    ws = text.split()
    if not ws or dur <= 0:
        return []
    step = (dur * 1000) / len(ws)
    return [{"text": w, "start_ms": int(i * step), "end_ms": int((i + 1) * step)}
            for i, w in enumerate(ws)]
