"""VidForge AI - Built-in research browser (Playwright, auto-detected Chrome/Edge).

Purpose: let the AI agent (and the user) fetch REAL images/video footage of the
events discussed in a video — search pages, article hero images, og-video tags,
archive pages — and pull them into the project media pool with license notes.
Falls back to plain requests scraping if Playwright is unavailable.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import urllib.parse

import requests

from . import config

log = logging.getLogger("vidforge.browser")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 VidForgeAI/2.0"


def _has_playwright() -> bool:
    try:
        from .runtime import playwright_available
        return playwright_available()
    except Exception:
        return False


class ForgeBrowser:
    """Headless-capable browser session with media-sniffing helpers."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw = None
        self._browser = None
        self.ctx = None
        self.page = None

    # ------------------------------------------------------------ lifecycle
    def start(self):
        if not _has_playwright():
            raise RuntimeError(
                "Research browser unavailable: run `python -m playwright install chromium` "
                "(inside VidForgeAI.exe this feature is optional - stock APIs cover sourcing)")
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        exe = config.CFG.get("chrome_path") or None
        try:
            self._browser = self._pw.chromium.launch(
                executable_path=exe, headless=self.headless)
        except Exception:
            # try msedge channel then bundled chromium
            for ch in ("msedge", "chrome"):
                try:
                    self._browser = self._pw.chromium.launch(channel=ch,
                                                             headless=self.headless)
                    break
                except Exception:
                    continue
            if not self._browser:
                self._browser = self._pw.chromium.launch(headless=self.headless)
        self.ctx = self._browser.new_context(user_agent=UA,
                                             viewport={"width": 1366, "height": 768})
        self.page = self.ctx.new_page()
        return self

    def stop(self):
        for closer in (lambda: self.ctx.close(), lambda: self._browser.close(),
                       lambda: self._pw.stop()):
            try:
                closer()
            except Exception:
                pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()

    # ------------------------------------------------------------ actions
    def goto(self, url: str, wait_ms: int = 1500):
        self.page.goto(url, timeout=45000, wait_until="domcontentloaded")
        self.page.wait_for_timeout(wait_ms)
        return self.page.title()

    def screenshot(self, path: str, full_page: bool = False) -> str:
        self.page.screenshot(path=path, full_page=full_page)
        return path

    def sniff_media(self) -> list[dict]:
        """Extract candidate images/videos from the current page DOM."""
        out = []
        html = self.page.content()
        # og / twitter video
        for m in re.finditer(r'(?:og:video|twitter:player:stream)"?\s+content="([^"]+)"', html):
            out.append({"kind": "video", "url": m.group(1), "how": "meta"})
        # <video src>/<source src>
        for m in re.finditer(r'<(?:video|source)[^>]+src="([^"]+\.(?:mp4|webm|m3u8)[^"]*)"', html):
            out.append({"kind": "video", "url": m.group(1), "how": "tag"})
        # big <img>s
        for m in re.finditer(r'<img[^>]+src="([^"]+)"[^>]*>', html):
            u = urllib.parse.urljoin(self.page.url, m.group(1))
            if re.search(r"\.(jpe?g|png|webp|avif)", u, re.I) and len(u) > 20:
                out.append({"kind": "image", "url": u, "how": "img"})
        uniq, seen = [], set()
        for a in out:
            if a["url"] not in seen:
                seen.add(a["url"])
                uniq.append(a)
        return uniq[:80]

    # ------------------------------------------------------------ searches
    def image_search(self, query: str, n: int = 12) -> list[dict]:
        """DuckDuckGo image results via the browser (no API key needed)."""
        self.goto("https://duckduckgo.com/?q=" + urllib.parse.quote_plus(query) +
                  "&iax=images&ia=images", wait_ms=2500)
        self.page.mouse.wheel(0, 1200)
        self.page.wait_for_timeout(1200)
        res = []
        urls = self.page.eval_on_selector_all(
            "a[href*='media'] , img[src^='http']",
            "els => els.map(e => e.href || e.src)")
        for u in urls or []:
            if u and re.match(r"https?://", u) and len(res) < n:
                res.append({"kind": "image", "url": u, "page": self.page.url})
        return res

    def close_current(self):
        try:
            self.page.close()
        except Exception:
            pass


# ------------------------------------------------------------------ fallback scraper
def quick_fetch_page(url: str) -> dict:
    """No-browser fallback: raw HTML media extraction."""
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    html = r.text
    vids = re.findall(r'"(https://[^"]+\.mp4[^"]*)"', html)
    imgs = [urllib.parse.urljoin(url, m) for m in
            re.findall(r'<img[^>]+src="([^"]+)"', html)]
    title = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    return {"title": title.group(1).strip() if title else url,
            "videos": vids[:20], "images": imgs[:40]}


def download_from_browser(asset_url: str, referer: str, dest_dir: str | None = None) -> str:
    from . import media_search
    ext = ".mp4" if re.search(r"\.mp4|\.webm", asset_url, re.I) else ".jpg"
    return media_search.download(asset_url, dest_dir=dest_dir, ext=ext, referer=referer)
