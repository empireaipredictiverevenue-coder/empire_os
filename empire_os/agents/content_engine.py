#!/usr/bin/env python3
"""
content_engine.py — CONTENT MOAT orchestrator.

1. scrapecreators_enrich  -> pull real businesses into si_buyer_outreach (intake)
2. article_writer         -> draft + spin buyer-intent AEO pages (traffic)
3. build_sitemap          -> regenerate /srv/aeo/sitemap.xml from ALL pages
4. submit_gsc             -> ping Google Search Console sitemap endpoint

This fixes the orphan leak: 210 AEO pages existed but sitemap.xml was EMPTY,
so GSC indexed nothing. Now every published page lands in the sitemap and is
submitted, driving organic traffic -> leads.

Runs as empire-content-engine.service (timer every 30 min, Restart=always).
"""
import os, sys, json, time, logging
# Add BOTH the agents/ dir (for sibling modules like article_writer) AND
# the parent empire_os/ dir (so `from empire_os.funnel import` resolves).
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import article_writer as AW
import scrapecreators_enrich as SC
import predictive_router as PR
from empire_os.aeo_surface import list_pages

log = logging.getLogger("content_engine")
SURFACE = os.getenv("AEO_SURFACE_ROOT", "/srv/aeo")
SITE = "https://empire-ai.co.uk"
GSC_CREDS = os.getenv("GSC_CREDS", "/root/.gsc-creds.json")
DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")


def build_sitemap() -> int:
    """Regenerate sitemap.xml from every published AEO page. Returns #urls.

    Walks niche dir index.html AND metro subdirs (/aeo/<niche>/<METRO>/).
    """
    pages = list_pages(SURFACE)
    urls = [f"{SITE}{p['url_path']}" for p in pages]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml.append(f"  <url><loc>{u}</loc></url>")
    xml.append("</urlset>")
    with open(os.path.join(SURFACE, "sitemap.xml"), "w") as f:
        f.write("\n".join(xml))
    log.info("sitemap rebuilt: %d urls (niches+metros)", len(urls))
    return len(urls)


def submit_gsc() -> str:
    """Submit sitemap to GSC via service-account JWT (no googleapiclient)."""
    try:
        import jwt, requests, datetime as dt
    except ImportError:
        return "skip: jwt/requests missing"
    if not os.path.exists(GSC_CREDS):
        return "skip: no GSC creds"
    try:
        sa = json.load(open(GSC_CREDS))
        iat = int(time.time())
        payload = {
            "iss": sa["client_email"], "scope":
            "https://www.googleapis.com/auth/webmasters",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": iat, "exp": iat + 3600,
        }
        tok = jwt.encode(payload, sa["private_key"], algorithm="RS256")
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": tok}, timeout=20)
        access = r.json().get("access_token")
        if not access:
            return f"gsc token err: {r.text[:120]}"
        site = "sc-domain:empire-ai.co.uk"
        resp = requests.post(
            f"https://www.googleapis.com/webmasters/v3/sites/{requests.utils.quote(site, safe='')}/sitemaps/https%3A%2F%2Fempire-ai.co.uk%2Fsitemap.xml",
            headers={"Authorization": f"Bearer {access}",
                      "Content-Type": "application/json"},
            json={}, timeout=20)
        return f"gsc submit: {resp.status_code}"
    except Exception as e:
        return f"gsc err: {str(e)[:140]}"


def tick(dry_run: bool = False) -> dict:
    out = {}
    try:
        out["scrape"] = SC.run(dry_run=dry_run, cap=8 if not dry_run else 8)
    except Exception as e:
        out["scrape"] = f"scrape skipped: {str(e)[:120]}"
    out["predict"] = PR.run(dry_run=dry_run)
    out["articles"] = AW.run(dry_run=dry_run, limit=3 if not dry_run else 3)
    if not dry_run:
        out["sitemap_urls"] = build_sitemap()
        out["gsc"] = submit_gsc()
    return out


if __name__ == "__main__":
    import argparse
    # robust .env loader (handles spaces/unquoted values)
    _env = os.getenv("EMPIRE_ENV", "/root/empire_os/.env")
    try:
        with open(_env) as _fh:
            for _line in _fh:
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    print(json.dumps(tick(dry_run=a.dry), indent=2))
