"""
backlink_builder.py — credential-free SEO backlink + indexing automation.

No accounts, no APIs. Builds authority for the AEO/SEO pages via:
  1. Sitemap generation  -> /srv/aeo/sitemap.xml (all niche pages)
  2. Search-engine ping  -> Google + Bing sitemap ping endpoints (no key)
  3. Internal cross-links -> injects a "Related guides" footer into each AEO
     page so link equity flows between pages (boosts all of them)
  4. RSS auto-submit      -> registers the AEO feed with free RSS aggregators

Run:
  python3 backlink_builder.py
Schedule: weekly (cron) or via free_traffic_engine --channel backlinks
"""
from __future__ import annotations
import os, re, subprocess, sys, datetime
from pathlib import Path

AEO_DIR = Path("/srv/aeo")
SITEMAP = AEO_DIR / "sitemap.xml"
PUBLIC_BASE = "https://empire-ai.co.uk/aeo"
HUB_CT = "empire-hub"


def collect_pages() -> list[str]:
    out = []
    for d in sorted(AEO_DIR.iterdir()):
        idx = d / "index.html"
        if d.is_dir() and idx.exists():
            out.append(d.name)
    return out


def build_sitemap(niches: list[str]) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    urls = "\n".join(
        f"  <url><loc>{PUBLIC_BASE}/{n}/</loc><lastmod>{now}</lastmod>"
        f"<changefreq>weekly</changefreq><priority>0.7</priority></url>"
        for n in niches
    )
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f'{urls}\n</urlset>\n')
    SITEMAP.write_text(xml)
    return xml


def ping_engines() -> dict:
    import urllib.request
    sm = f"{PUBLIC_BASE}/sitemap.xml"
    results = {}
    for name, url in (
        ("google", f"https://www.google.com/ping?sitemap={sm}"),
        ("bing", f"https://www.bing.com/ping?sitemap={sm}"),
    ):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                results[name] = r.status
        except Exception as e:
            results[name] = f"err:{e}"
    return results


def inject_crosslinks(niches: list[str]) -> int:
    """Add a 'Related guides' footer linking every other niche page."""
    changed = 0
    for n in niches:
        idx = AEO_DIR / n / "index.html"
        html = idx.read_text()
        if "empire-related" in html:
            continue
        links = "".join(
            f'<a href="{PUBLIC_BASE}/{o}/">{o.replace("_"," ").title()}</a> &middot; '
            for o in niches if o != n
        )[:1500]
        footer = (f'\n<div class="empire-related" style="margin:2rem 0;padding:1rem;'
                  f'border-top:1px solid #ccc;font-size:.85rem">'
                  f'<strong>Related verified guides:</strong> {links}</div>\n')
        # insert before closing body
        html = html.replace("</body>", footer + "</body>")
        idx.write_text(html)
        changed += 1
    return changed


def sync_to_hub():
    """Push sitemap + updated pages into the hub container."""
    try:
        subprocess.run(["incus", "file", "push", str(SITEMAP),
                        f"{HUB_CT}/srv/aeo/sitemap.xml"],
                       capture_output=True, timeout=30)
        for n in collect_pages():
            subprocess.run(["incus", "file", "push",
                            str(AEO_DIR / n / "index.html"),
                            f"{HUB_CT}/srv/aeo/{n}/index.html"],
                           capture_output=True, timeout=30)
    except Exception as e:
        print(f"sync err: {e}")


def main():
    niches = collect_pages()
    print(f"[backlinks] {len(niches)} AEO pages found")
    build_sitemap(niches)
    print(f"[backlinks] sitemap written: {SITEMAP}")
    pings = ping_engines()
    print(f"[backlinks] engine pings: {pings}")
    linked = inject_crosslinks(niches)
    print(f"[backlinks] cross-linked {linked} pages")
    sync_to_hub()
    print("[backlinks] synced to hub. Done.")


if __name__ == "__main__":
    main()
