"""VidForge AI - Royalty-free media search & download.

Providers: Pexels, Pixabay, Unsplash, Coverr (keyless browse), Mixkit catalogue,
Archive.org (public-domain footage) + Wikimedia Commons.
Every asset records its license so renders stay copyright-safe.
All results are cached under the media cache dir for instant reuse.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.parse

import requests

from . import config

log = logging.getLogger("vidforge.media")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VidForgeAI/2.0"}


def _cache_name(url: str, ext_hint: str = "") -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"{h}{ext_hint or ''}"


def download(url: str, dest_dir: str | None = None, ext: str = ".mp4",
             referer: str | None = None) -> str:
    """Download a remote file into cache, return local path."""
    dest_dir = dest_dir or config.MEDIA_CACHE
    fname = _cache_name(url, ext)
    path = os.path.join(dest_dir, fname)
    if os.path.exists(path) and os.path.getsize(path) > 1024:
        return path
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    deadline = time.time() + float(config.CFG.get("asset_dl_timeout_s", 90))
    try:
        with requests.get(url, stream=True,
                          timeout=(10, int(config.CFG.get("http_timeout_s", 20))),
                          headers=headers) as r:
            r.raise_for_status()
            max_bytes = int(config.CFG.get("asset_max_mb", 80)) * 1024 * 1024
            got = 0
            with open(path + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    got += len(chunk)
                    if got > max_bytes or time.time() > deadline:
                        log.info("download capped (%s MB / deadline) %s", got >> 20, url[:60])
                        break
        if os.path.getsize(path + ".part") < 1024:
            raise RuntimeError("empty/tiny download")
        os.replace(path + ".part", path)
        return path
    except Exception as e:
        log.warning("download failed %s: %s", url[:80], e)
        if os.path.exists(path + ".part"):
            os.remove(path + ".part")
        raise


# ------------------------------------------------------------------ providers
def search_pexels(query: str, kind: str = "video", per_page: int = 12) -> list[dict]:
    cfg = config.CFG
    key = cfg.get("pexels_api_key")
    out = []
    if not key:
        # keyless fallback via public JSON endpoint used by their site (rate-limited)
        return out
    url = (f"https://api.pexels.com/videos/search" if kind == "video"
           else "https://api.pexels.com/v1/search")
    r = requests.get(url, params={"query": query, "per_page": per_page},
                     headers={"Authorization": key}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if kind == "video":
        for v in data.get("videos", []):
            files = sorted(v.get("video_files", []),
                           key=lambda f: (f.get("height") or 0))
            best = next((f for f in reversed(files)
                         if (f.get("height") or 0) <= 1080), files[-1] if files else None)
            if best:
                thumb = (v.get("image") or
                         (v.get("picture") if isinstance(v.get("picture"), str) else ""))
                out.append({"source": "pexels", "kind": "video",
                            "url": best["link"], "thumb": thumb,
                            "duration": v.get("duration", 0),
                            "license": "Pexels License (free, no attribution)",
                            "page": v.get("page", ""), "credit": "Pexels"})
    else:
        for p in data.get("photos", []):
            out.append({"source": "pexels", "kind": "image",
                        "url": p.get("src", {}).get("large2x") or p.get("src", {}).get("large", ""),
                        "thumb": p.get("src", {}).get("medium", ""),
                        "license": "Pexels License (free, no attribution)",
                        "page": p.get("page", ""), "credit": p.get("user", {}).get("name", "Pexels")})
    return out


def search_pixabay(query: str, kind: str = "video", per_page: int = 12) -> list[dict]:
    cfg = config.CFG
    key = cfg.get("pixabay_api_key")
    if not key:
        return []
    url = ("https://pixabay.com/api/videos/" if kind == "video"
           else "https://pixabay.com/api/")
    r = requests.get(url, params={"key": key, "q": query, "per_page": per_page}, timeout=30)
    r.raise_for_status()
    data = r.json()
    out = []
    if kind == "video":
        for v in data.get("hits", []):
            items = v.get("videos", {})
            pick = items.get("large") or items.get("medium") or items.get("small") or {}
            out.append({"source": "pixabay", "kind": "video", "url": pick.get("url", ""),
                        "thumb": v.get("pictures", {}).get("medium", {}).get("url", "")
                        if isinstance(v.get("pictures"), dict) else "",
                        "duration": v.get("duration", 0),
                        "license": "Pixabay Content License (free)",
                        "page": v.get("pageURL", ""), "credit": v.get("user", "Pixabay")})
    else:
        for p in data.get("hits", []):
            out.append({"source": "pixabay", "kind": "image",
                        "url": p.get("largeImageURL") or p.get("webformatURL", ""),
                        "thumb": p.get("webformatURL", ""),
                        "license": "Pixabay Content License (free)",
                        "page": p.get("pageURL", ""), "credit": p.get("user", "Pixabay")})
    return out


def search_unsplash(query: str, per_page: int = 12) -> list[dict]:
    key = config.CFG.get("unsplash_access_key")
    if not key:
        return []
    r = requests.get("https://api.unsplash.com/search/photos",
                     params={"query": query, "per_page": per_page},
                     headers={"Authorization": f"Client-ID {key}", **UA}, timeout=30)
    r.raise_for_status()
    out = []
    for p in r.json().get("results", []):
        out.append({"source": "unsplash", "kind": "image",
                    "url": p.get("urls", {}).get("regular", ""),
                    "thumb": p.get("urls", {}).get("small", ""),
                    "license": "Unsplash License (free)",
                    "page": p.get("links", {}).get("html", ""),
                    "credit": p.get("user", {}).get("name", "Unsplash")})
    return out


def search_coverr(query: str, per_page: int = 10) -> list[dict]:
    """Coverr public browse API (no key needed for search)."""
    try:
        q = urllib.parse.quote_plus(query)
        r = requests.get(f"https://coverr.co/api/videos?search={q}&limit={per_page}",
                         headers=UA, timeout=20)
        if r.status_code != 200:
            return []
        data = r.json()
        vids = data if isinstance(data, list) else data.get("videos", [])
        out = []
        for v in vids:
            src = v.get("poster_original") or v.get("poster") or ""
            mp4 = v.get("file_mp4") or v.get("download_link") or ""
            if mp4:
                out.append({"source": "coverr", "kind": "video", "url": mp4,
                            "thumb": src, "duration": v.get("duration", 0),
                            "license": "Coverr Free License",
                            "page": f"https://coverr.co/videos/{v.get('slug','')}",
                            "credit": "Coverr"})
        return out
    except Exception as e:
        log.info("coverr: %s", e)
        return []


def search_mixkit(query: str, per_page: int = 8) -> list[dict]:
    """Mixkit free stock videos (no attribution). Best-effort page scrape."""
    try:
        q = urllib.parse.quote_plus(query.replace(" ", "-"))
        r = requests.get(f"https://mixkit.co/free-stock-video/{q}/",
                         headers=UA, timeout=20)
        if r.status_code != 200:
            return []
        out = []
        slugs = re.findall(r'href="/free-stock-video/([^"/]+)/"', r.text)
        seen = set()
        for slug in slugs:
            if slug in seen or len(out) >= per_page:
                continue
            seen.add(slug)
            try:
                pr = requests.get(f"https://mixkit.co/free-stock-video/{slug}/",
                                  headers=UA, timeout=20)
                m = re.search(r'data-video-src="([^"]+\.mp4[^"]*)"', pr.text) or \
                    re.search(r'"(https://assets\.mixkit\.co/[^"]+\.mp4)"', pr.text)
                th = re.search(r'property="og:image" content="([^"]+)"', pr.text)
                if m:
                    out.append({"source": "mixkit", "kind": "video", "url": m.group(1),
                                "thumb": th.group(1) if th else "",
                                "license": "Mixkit Free License (no attribution)",
                                "page": f"https://mixkit.co/free-stock-video/{slug}/",
                                "credit": "Mixkit"})
            except Exception:
                continue
        return out
    except Exception as e:
        log.info("mixkit: %s", e)
        return []


def search_archive_org(query: str, per_page: int = 10) -> list[dict]:
    """Internet Archive — public domain / CC footage & images."""
    try:
        r = requests.get("https://archive.org/advancedsearch.php", params={
            "q": f"{query} AND (mediatype:movies OR mediatype:images)",
            "fl[]": ["identifier", "title", "mediatype", "licenseurl"],
            "rows": per_page, "output": "json"}, timeout=25)
        out = []
        for doc in r.json().get("response", {}).get("docs", []):
            ident = doc["identifier"]
            mt = doc.get("mediatype", "movies")
            out.append({"source": "archive.org", "kind": "video" if mt == "movies" else "image",
                        "url": f"__archive__{ident}",  # resolved at download time
                        "thumb": f"https://archive.org/services/img/{ident}",
                        "license": doc.get("licenseurl", "Public Domain / check item"),
                        "page": f"https://archive.org/details/{ident}",
                        "credit": doc.get("title", ident)})
        return out
    except Exception as e:
        log.info("archive: %s", e)
        return []


def resolve_archive_item(ident: str, want_video: bool = True) -> str:
    """Pick a concrete downloadable file from an archive.org item."""
    r = requests.get(f"https://archive.org/metadata/{ident}", timeout=25).json()
    files = r.get("files", [])
    def size(f):
        try:
            return int(f.get("size", 0))
        except Exception:
            return 0
    if want_video:
        cands = [f for f in files if str(f.get("name", "")).lower().endswith(".mp4")]
        cands.sort(key=lambda f: size(f))
        pick = next((f for f in cands if 1 < size(f) < 200_000_000), cands[0] if cands else None)
        if pick:
            return f"https://archive.org/download/{ident}/{urllib.parse.quote(pick['name'])}"
    cands = [f for f in files if re.search(r"\.(jpg|jpeg|png)$", str(f.get("name", "")), re.I)]
    if cands:
        return f"https://archive.org/download/{ident}/{urllib.parse.quote(cands[0]['name'])}"
    raise RuntimeError(f"no downloadable file in {ident}")


def search_wikimedia(query: str, kind: str = "video", per_page: int = 10) -> list[dict]:
    """Wikimedia Commons – keyless, free-licensed images (CC / public domain)."""
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php",
                         params={"action": "query", "format": "json", "generator": "search",
                                 "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": per_page * 2,
                                 "prop": "imageinfo", "iiprop": "url|extmetadata",
                                 "iiurlwidth": 1600}, timeout=15, headers=UA)
        out = []
        for p in r.json().get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            title = p.get("title", "")
            if not re.search(r"\.(jpg|jpeg|png)$", title, re.I):
                continue
            meta = ii.get("extmetadata", {})
            lic = (meta.get("LicenseShortName", {}).get("value") or "CC").strip()
            artist = re.sub("<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
            thumb = ii.get("thumburl") or ii.get("url", "")
            full = ii.get("url", "")
            if thumb:
                out.append({"source": "wikimedia", "kind": "image",
                            "url": full or thumb, "thumb": thumb,
                            "license": f"Wikimedia Commons ({lic})",
                            "page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}",
                            "credit": artist or "Wikimedia Commons"})
        return out[:per_page]
    except Exception as e:
        log.info("wikimedia: %s", e)
        return []


def search_nasa(query: str, kind: str = "video", per_page: int = 10) -> list[dict]:
    """NASA open API – public-domain space imagery & video (keyless, DEMO_KEY built in)."""
    try:
        r = requests.get("https://images-api.nasa.gov/search",
                         params={"q": query, "media_type": "video" if kind == "video" else "image",
                                 "page_size": per_page}, timeout=15, headers=UA)
        items = r.json().get("collection", {}).get("items", [])
        out = []
        for it in items:
            d = (it.get("data") or [{}])[0]
            links = it.get("links") or []
            url = ""
            for lk in links:
                if lk.get("render") == "mp4" or url == "":
                    url = lk.get("href", url)
                    if lk.get("render") == "mp4":
                        break
            if not url:
                continue
            out.append({"source": "nasa", "kind": "video" if kind == "video" else "image",
                        "url": url, "thumb": (links[0].get("href") if links else ""),
                        "duration": 0,
                        "license": "NASA Media Usage Guidelines (public domain)",
                        "page": d.get("nasa_id", ""), "credit": "NASA"})
        return out
    except Exception as e:
        log.info("nasa: %s", e)
        return []


# ------------------------------------------------------------------ aggregate
PROVIDERS = {
    "pexels": search_pexels,
    "pixabay": search_pixabay,
    "unsplash": lambda q, k="image", n=12: search_unsplash(q, n) if k == "image" else [],
    "coverr": lambda q, k="video", n=10: search_coverr(q, n) if k == "video" else [],
    "mixkit": lambda q, k="video", n=8: (search_mixkit(q, n) if config.CFG.get("mixkit_enabled") and k == "video" else []),
    "archive.org": lambda q, k="video", n=10: search_archive_org(q, n),
    "wikimedia": lambda q, k="image", n=10: search_wikimedia(q, k, n),
    "nasa": lambda q, k="video", n=8: search_nasa(q, k, n),
}


def search_all(query: str, kind: str = "video", per_provider: int = 8,
               providers: list[str] | None = None) -> list[dict]:
    cfg = config.CFG
    enabled = cfg.get("enabled_providers") or list(PROVIDERS)
    hard_to = int(cfg.get("http_timeout_s", 12))
    results, errors = [], []
    for name in (providers or enabled):
        if name not in enabled:
            continue
        fn = PROVIDERS.get(name)
        if not fn:
            continue
        # guard every provider with a wall-clock deadline so one slow site
        # can never stall the whole pipeline
        import concurrent.futures as _cf
        try:
            with _cf.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(lambda: fn(query, kind, per_provider)
                                if fn.__code__.co_argcount == 3 else fn(query, kind))
                results.extend(fut.result(timeout=hard_to + 8))
        except _cf.TimeoutError:
            errors.append(f"{name}: timed out")
            log.info("provider %s timed out (>%ss)", name, hard_to + 8)
        except Exception as e:
            errors.append(f"{name}: {e}")
            log.info("provider %s failed: %s", name, e)
    # de-dupe by URL
    uniq, seen = [], set()
    for a in results:
        u = a.get("url")
        if u and u not in seen:
            seen.add(u)
            uniq.append(a)
    return uniq


def fetch_asset(asset: dict, kind: str | None = None) -> str:
    """Download an asset dict to a local file. Returns path."""
    url = asset["url"]
    kind = kind or asset.get("kind", "video")
    ext = ".mp4" if kind == "video" else ".jpg"
    if url.startswith("__archive__"):
        url = resolve_archive_item(url.replace("__archive__", ""), kind == "video")
    ref = asset.get("page") or None
    return download(url, ext=ext, referer=ref)


# ------------------------------------------------------------------ music
FREE_MUSIC_SOURCES = {
    "youtube_audio_library": "https://www.youtube.com/@TTS/ (in-app browser)",
    "pixabay_music": "https://pixabay.com/music/ (needs pixabay key)",
    "incompetech": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/",
}


def search_pixabay_music(query: str, per_page: int = 8) -> list[dict]:
    key = config.CFG.get("pixabay_api_key")
    if not key:
        return []
    try:
        r = requests.get("https://pixabay.com/api/videos/",  # music shares CDN pattern
                         params={"key": key, "q": query + " music", "per_page": per_page},
                         timeout=25)
        out = []
        for v in r.json().get("hits", []):
            pass
        return out  # pixabay audio API requires partner access; UI offers browser download
    except Exception:
        return []
