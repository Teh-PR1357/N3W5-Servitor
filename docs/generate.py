#!/usr/bin/env python3
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import urlopen, Request

SITEMAP_URL = "https://www.warhammer-community.com/sitemap.xml"
ARTICLE_RE = re.compile(r"^https://www\.warhammer-community\.com/en-gb/articles/")
MAX_ITEMS = 50

def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (RSS generator)"})
    with urlopen(req, timeout=30) as r:
        return r.read()

def rfc2822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

def main():
    xml_bytes = fetch(SITEMAP_URL)
    root = ET.fromstring(xml_bytes)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    items = []
    for url_el in root.findall("sm:url", ns):
        loc_el = url_el.find("sm:loc", ns)
        lastmod_el = url_el.find("sm:lastmod", ns)
        if loc_el is None:
            continue
        loc = (loc_el.text or "").strip()
        if not ARTICLE_RE.match(loc):
            continue

        lastmod = None
        if lastmod_el is not None and lastmod_el.text:
            t = lastmod_el.text.strip().replace("Z", "+00:00")
            try:
                lastmod = datetime.fromisoformat(t)
            except Exception:
                lastmod = None

        items.append((lastmod or datetime.now(timezone.utc), loc))

    items.sort(key=lambda x: x[0], reverse=True)
    items = items[:MAX_ITEMS]

    now = datetime.now(timezone.utc)

    rss = []
    rss.append('<?xml version="1.0" encoding="UTF-8"?>')
    rss.append('<rss version="2.0">')
    rss.append("<channel>")
    rss.append("<title>Warhammer Community – All News (sitemap-based)</title>")
    rss.append("<link>https://www.warhammer-community.com/en-gb/all-news-and-features/</link>")
    rss.append("<description>Unofficial RSS generated from Warhammer Community sitemap.xml</description>")
    rss.append(f"<lastBuildDate>{rfc2822(now)}</lastBuildDate>")

    for dt, loc in items:
        pub = dt.astimezone(timezone.utc)
        slug = loc.rstrip("/").split("/")[-1]
        rss.append("<item>")
        rss.append(f"<title>{slug}</title>")
        rss.append(f"<link>{loc}</link>")
        rss.append(f"<guid isPermaLink=\"true\">{loc}</guid>")
        rss.append(f"<pubDate>{rfc2822(pub)}</pubDate>")
        rss.append("</item>")

    rss.append("</channel></rss>")

    with open("docs/rss.xml", "wb") as f:
        f.write("\n".join(rss).encode("utf-8"))

if __name__ == "__main__":
    main()
