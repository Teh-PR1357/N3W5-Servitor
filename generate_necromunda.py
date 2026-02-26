#!/usr/bin/env python3
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import urlopen, Request

# --- Settings ---
SITEMAP_URL = "https://www.warhammer-community.com/sitemap.xml"
ARTICLE_RE = re.compile(r"^https://www\.warhammer-community\.com/en-gb/articles/")

MAX_ITEMS = 50          # wie viele Items im Feed landen
MAX_SCAN = 200          # wie viele der neuesten Artikel max. geprüft werden (Performance-Limit)

NECRO_MARKERS = [
    "/topics/necromunda/",
    "/setting/necromunda/",
    ">Necromunda<",
    '"Necromunda"',
]

OUTPUT_PATH = "docs/necromunda.xml"
CHANNEL_TITLE = "Warhammer Community – Necromunda"
CHANNEL_LINK = "https://www.warhammer-community.com/en-gb/setting/necromunda/"
CHANNEL_DESC = "Necromunda-only RSS feed (sitemap-based, filtered)"

# --- Helpers ---
def fetch(url: str) -> bytes:
    req = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (RSS generator; github actions)"},
    )
    with urlopen(req, timeout=30) as r:
        return r.read()

def rfc2822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

def parse_lastmod(lastmod_text: str) -> datetime | None:
    # example: 2024-09-17T15:12:09.000000Z
    t = lastmod_text.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(t)
    except Exception:
        return None

def slug_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1] or url

# --- Main ---
def main():
    xml_bytes = fetch(SITEMAP_URL)
    root = ET.fromstring(xml_bytes)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    candidates: list[tuple[datetime, str]] = []

    # 1) Collect candidates from sitemap (no HTML fetch yet)
    for url_el in root.findall("sm:url", ns):
        loc_el = url_el.find("sm:loc", ns)
        lastmod_el = url_el.find("sm:lastmod", ns)

        if loc_el is None or not loc_el.text:
            continue

        loc = loc_el.text.strip()
        if not ARTICLE_RE.match(loc):
            continue

        dt = datetime.now(timezone.utc)
        if lastmod_el is not None and lastmod_el.text:
            parsed = parse_lastmod(lastmod_el.text)
            if parsed is not None:
                dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

        candidates.append((dt, loc))

    # 2) newest first
    candidates.sort(key=lambda x: x[0], reverse=True)

    # 3) Filter by Necromunda, but only scan newest MAX_SCAN to keep runtime bounded
    items: list[tuple[datetime, str]] = []
    for dt, loc in candidates[:MAX_SCAN]:
        try:
            html = fetch(loc).decode("utf-8", errors="ignore").lower()
        except Exception:
            continue

        if not any(m.lower() in html for m in NECRO_MARKERS):
            continue

        items.append((dt, loc))
        if len(items) >= MAX_ITEMS:
            break

    # 4) Build RSS
    now = datetime.now(timezone.utc)

    rss: list[str] = []
    rss.append('<?xml version="1.0" encoding="UTF-8"?>')
    rss.append('<rss version="2.0">')
    rss.append("<channel>")
    rss.append(f"<title>{CHANNEL_TITLE}</title>")
    rss.append(f"<link>{CHANNEL_LINK}</link>")
    rss.append(f"<description>{CHANNEL_DESC}</description>")
    rss.append(f"<lastBuildDate>{rfc2822(now)}</lastBuildDate>")

    for dt, loc in items:
        rss.append("<item>")
        rss.append(f"<title>{slug_from_url(loc)}</title>")
        rss.append(f"<link>{loc}</link>")
        rss.append(f"<guid isPermaLink=\"true\">{loc}</guid>")
        rss.append(f"<pubDate>{rfc2822(dt.astimezone(timezone.utc))}</pubDate>")
        rss.append("</item>")

    rss.append("</channel></rss>")

    # Ensure output directory exists (GitHub Actions also does mkdir -p docs, but no harm)
    # Writing file
    with open(OUTPUT_PATH, "wb") as f:
        f.write("\n".join(rss).encode("utf-8"))

if __name__ == "__main__":
    main()
