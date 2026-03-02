#!/usr/bin/env python3
import re
import html as html_lib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from pathlib import Path

FORCE_KICK_ONCE = True

# --- Settings ---
SITEMAP_URL = "https://www.warhammer-community.com/sitemap.xml"
ARTICLE_RE = re.compile(r"^https://www\.warhammer-community\.com/en-gb/articles/")

MAX_ITEMS = 150
OUTPUT_PATH = "docs/rss.xml"

CHANNEL_TITLE = "N3W5-Servitor – Warhammer News"
CHANNEL_LINK = "https://www.warhammer-community.com/en-gb/all-news-and-features/"
CHANNEL_DESC = "Unofficial RSS generated from Warhammer Community sitemap.xml (titles extracted)"

# First-run marker (committed to repo by Actions)
FIRST_RUN_MARKER = Path("docs/.first_run_done_allnews")

# --- Helpers ---
def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (RSS generator; github actions)"})
    with urlopen(req, timeout=30) as r:
        return r.read()

def rfc2822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

def parse_lastmod(lastmod_text: str) -> datetime | None:
    t = lastmod_text.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(t)
    except Exception:
        return None

def xml_escape(s: str) -> str:
    return html_lib.escape(s, quote=True)

def extract_title(page_html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", page_html, re.IGNORECASE | re.DOTALL)
    if not m:
        return "Warhammer Community"
    title = m.group(1)
    title = re.sub(r"\s*\|\s*Warhammer Community.*$", "", title, flags=re.IGNORECASE)
    title = html_lib.unescape(title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or "Warhammer Community"

# --- Main ---
def main():
    # First run => only publish 1 newest item (prevents backlog spam on bot attach)
    is_first_run = not FIRST_RUN_MARKER.exists()
    target_count = MAX_ITEMS
    
    xml_bytes = fetch(SITEMAP_URL)
    root = ET.fromstring(xml_bytes)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    candidates: list[tuple[datetime, str]] = []

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

    candidates.sort(key=lambda x: x[0], reverse=True)
    items = candidates[:target_count]

    now = datetime.now(timezone.utc)

    rss: list[str] = []
    rss.append('<?xml version="1.0" encoding="UTF-8"?>')
    rss.append('<rss version="2.0">')
    rss.append("<channel>")
    rss.append(f"<title>{xml_escape(CHANNEL_TITLE)}</title>")
    rss.append(f"<link>{xml_escape(CHANNEL_LINK)}</link>")
    rss.append(f"<description>{xml_escape(CHANNEL_DESC)}</description>")
    rss.append(f"<lastBuildDate>{rfc2822(now)}</lastBuildDate>")

    for dt, loc in items:
        try:
            page_html = fetch(loc).decode("utf-8", errors="ignore")
            title = extract_title(page_html)
        except Exception:
            title = loc.rstrip("/").split("/")[-1] or "Warhammer Community"

        rss.append("<item>")
        rss.append(f"<title>{xml_escape(title)}</title>")
        rss.append(f"<link>{xml_escape(loc)}</link>")
        
        guid = loc

       # Kick nur beim ersten Item (neuester Artikel) und nur wenn FORCE aktiv ist
       if FORCE_KICK_ONCE and (dt, loc) == items[0]:
       guid = loc + "#kick1"

       rss.append(f"<guid isPermaLink=\"true\">{xml_escape(guid)}</guid>")
       rss.append(f"<pubDate>{rfc2822(dt.astimezone(timezone.utc))}</pubDate>")
       rss.append("</item>")

    rss.append("</channel></rss>")

    Path("docs").mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "wb") as f:
        f.write("\n".join(rss).encode("utf-8"))

    # Create marker AFTER first successful build
    if is_first_run:
        FIRST_RUN_MARKER.write_text("done\n", encoding="utf-8")

if __name__ == "__main__":
    main()
