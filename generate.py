#!/usr/bin/env python3
import re
import html as html_lib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import urlopen, Request

# --- Settings ---
SITEMAP_URL = "https://www.warhammer-community.com/sitemap.xml"
ARTICLE_RE = re.compile(r"^https://www\.warhammer-community\.com/en-gb/articles/")

MAX_ITEMS = 50
OUTPUT_PATH = "docs/rss.xml"

CHANNEL_TITLE = "N3W5-Servitor – All News"
CHANNEL_LINK = "https://www.warhammer-community.com/en-gb/all-news-and-features/"
CHANNEL_DESC = "Unofficial RSS generated from Warhammer Community sitemap.xml (titles extracted)"

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

def xml_escape(s: str) -> str:
    # RSS is XML; escape &, <, >, quotes etc.
    return html_lib.escape(s, quote=True)

def extract_title(page_html: str) -> str:
    """
    Pulls the <title>...</title> content and strips the common suffix.
    Falls back to a generic name if not found.
    """
    m = re.search(r"<title>(.*?)</title>", page_html, re.IGNORECASE | re.DOTALL)
    if not m:
        return "Warhammer Community"
    title = m.group(1)
    # Remove suffix like " | Warhammer Community"
    title = re.sub(r"\s*\|\s*Warhammer Community.*$", "", title, flags=re.IGNORECASE)
    # Decode HTML entities (&amp; etc.)
    title = html_lib.unescape(title)
    # Normalize whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title or "Warhammer Community"

# --- Main ---
def main():
    xml_bytes = fetch(SITEMAP_URL)
    root = ET.fromstring(xml_bytes)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    candidates: list[tuple[datetime, str]] = []

    # 1) Collect article URLs + lastmod from sitemap
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

    # 2) Newest first, keep top MAX_ITEMS
    candidates.sort(key=lambda x: x[0], reverse=True)
    items = candidates[:MAX_ITEMS]

    # 3) Build RSS
    now = datetime.now(timezone.utc)

    rss: list[str] = []
    rss.append('<?xml version="1.0" encoding="UTF-8"?>')
    rss.append('<rss version="2.0">')
    rss.append("<channel>")
    rss.append(f"<title>{xml_escape(CHANNEL_TITLE)}</title>")
    rss.append(f"<link>{xml_escape(CHANNEL_LINK)}</link>")
    rss.append(f"<description>{xml_escape(CHANNEL_DESC)}</description>")
    rss.append(f"<lastBuildDate>{rfc2822(now)}</lastBuildDate>")

    # We fetch each article page (only MAX_ITEMS) to extract a human title
    for dt, loc in items:
        try:
            page_html = fetch(loc).decode("utf-8", errors="ignore")
            title = extract_title(page_html)
        except Exception:
            # Fallback if the fetch fails for a specific item
            title = loc.rstrip("/").split("/")[-1] or "Warhammer Community"

        rss.append("<item>")
        rss.append(f"<title>{xml_escape(title)}</title>")
        rss.append(f"<link>{xml_escape(loc)}</link>")
        rss.append(f"<guid isPermaLink=\"true\">{xml_escape(loc)}</guid>")
        rss.append(f"<pubDate>{rfc2822(dt.astimezone(timezone.utc))}</pubDate>")
        rss.append("</item>")

    rss.append("</channel></rss>")

    with open(OUTPUT_PATH, "wb") as f:
        f.write("\n".join(rss).encode("utf-8"))

if __name__ == "__main__":
    main()
