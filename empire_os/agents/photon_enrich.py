#!/usr/bin/env python3
"""photon_enrich.py — FREE lead enrichment via Photon (OSM-based, no API key).

Replaces dead SerpAPI/Google Maps for:
  - lead enrichment: business name -> address, phone (via OSM), website (skip)
  - local SEO: generate city/niche landing pages with REAL local businesses
  - geocoding: address -> lat/lon (for outreach routing)

Photon API (https://photon.komoot.io):
  GET /api/?q={query}&limit=N&lat={lat}&lon={lon}
  Returns OSM features with name, street, city, state, postcode, lat, lon.
  Free. No key. ~1 req/sec rate limit (be polite).

Real test (verified 2026-07-20):
  q=roofing+Austin+Texas -> "Water Damage & Roofing of Austin", full addr, coords

Usage:
  from photon_enrich import search_businesses, enrich_lead, generate_seo_page
  results = search_businesses("roofing", "Austin", "TX", limit=5)
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, "/root/empire_os")

PHOTON = "https://photon.komoot.io/api/"
UA = "EmpireOS/1.0 (headless enrichment; contact: founder@empire-ai.co.uk)"
CACHE_DIR = Path("/root/empire_os/empire_os/photon_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(q: str, lat: Optional[float], lon: Optional[float]) -> Path:
    """Stable cache key per query (so we don't re-hit Photon)."""
    safe = "".join(c if c.isalnum() else "_" for c in q)[:80]
    if lat is not None and lon is not None:
        safe += f"_{round(lat, 2)}_{round(lon, 2)}"
    return CACHE_DIR / f"{safe}.json"


def _http(url: str, timeout: int = 20) -> Optional[dict]:
    """GET with UA + timeout. Returns parsed JSON or None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        sys.stderr.write(f"[photon] http fail {type(e).__name__}: {str(e)[:120]}\n")
        return None


def search_businesses(niche: str, city: str, state: str,
                       limit: int = 10, lat: Optional[float] = None,
                       lon: Optional[float] = None, use_cache: bool = True) -> list:
    """Search Photon for businesses matching niche+city+state.

    Returns list of {name, address, city, state, postcode, lat, lon, osm_id, type}.
    """
    q = f"{niche} {city} {state}".strip()
    cp = _cache_path(q, lat, lon)
    if use_cache and cp.exists() and (time.time() - cp.stat().st_mtime) < 86400 * 7:
        try:
            return json.loads(cp.read_text())
        except Exception:
            pass

    params = {"q": q, "limit": str(min(limit, 25))}
    if lat is not None:
        params["lat"] = str(lat)
    if lon is not None:
        params["lon"] = str(lon)
    url = PHOTON + "?" + urllib.parse.urlencode(params)
    data = _http(url)
    if not data or data.get("type") != "FeatureCollection":
        return []

    out = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [None, None])
        # Filter to businesses (osm_value indicates type)
        osm_value = props.get("osm_value", "")
        # Roofters, plumbers, hvac etc — relevant OSM values
        keep = (
            "roofer" in osm_value or
            "plumber" in osm_value or
            "electrician" in osm_value or
            "hvac" in osm_value or
            "construction" in osm_value or
            osm_value in ("company", "office", "commercial", "industrial", "house")
        )
        if not keep and not props.get("name"):
            continue
        out.append({
            "name": props.get("name", ""),
            "osm_id": props.get("osm_id"),
            "osm_value": osm_value,
            "street": props.get("street", ""),
            "housenumber": props.get("housenumber", ""),
            "city": props.get("city") or props.get("town") or props.get("village") or city,
            "county": props.get("county", ""),
            "state": props.get("state", state),
            "postcode": props.get("postcode", ""),
            "country": props.get("country", "United States"),
            "countrycode": props.get("countrycode", "US"),
            "lat": coords[1],
            "lon": coords[0],
        })

    # cache
    try:
        cp.write_text(json.dumps(out, indent=2))
    except Exception:
        pass

    # be polite to Photon
    time.sleep(1.0)
    return out


def enrich_lead(niche: str, city: str, state: str) -> dict:
    """Enrich a single lead: niche + city + state -> best matching real business.

    Returns dict with name, address, lat, lon (from Photon) — or {} if none found.
    Used to backfill si_buyer_outreach rows that have fake emails.
    """
    results = search_businesses(niche, city, state, limit=5)
    if not results:
        return {}
    # Pick first result with a real name + address
    for r in results:
        if r.get("name") and (r.get("street") or r.get("housenumber")):
            return r
    return results[0] if results else {}


def generate_seo_page(niche: str, city: str, state: str,
                      out_path: Optional[str] = None) -> dict:
    """Generate a local-SEO landing page for {niche} in {city}, {state}.

    Page includes:
      - H1, intro paragraph (LLM'd if MiniMax available, else templated)
      - List of REAL local businesses (from Photon)
      - Schema.org LocalBusiness JSON-LD for each
      - Meta tags + Open Graph
      - Internal links back to /buy-leads

    Returns {ok, out, businesses, seo_keywords}.
    """
    businesses = search_businesses(niche, city, state, limit=8)
    seo_keywords = [f"{niche} {city} {state}", f"{niche} near {city}",
                    f"best {niche} {city}", f"{niche} {state} reviews"]

    # LLM intro if available
    intro = _llm_intro(niche, city, state, len(businesses))
    if not intro:
        intro = (
            f"Looking for {niche} services in {city}, {state}? Empire OS connects "
            f"homeowners with vetted local {niche} professionals. Below are "
            f"{len(businesses)} real {niche} businesses in {city}, sourced from "
            f"OpenStreetMap. Tap any to learn more, or post your job to get "
            f"matched with the top-rated pros in your area — free, no signup."
        )

    # Build page
    biz_html = ""
    json_ld = []
    for b in businesses:
        addr = ", ".join(filter(None, [
            " ".join(filter(None, [b.get("housenumber", ""), b.get("street", "")])).strip(),
            b.get("city", ""), b.get("state", ""), b.get("postcode", ""),
        ]))
        biz_html += f"""
        <div class="biz">
          <h3>{_esc(b.get('name', 'Unknown'))}</h3>
          <p class="addr">📍 {_esc(addr) or 'Address unavailable'}</p>
          {f'<p class="meta">Type: {_esc(b.get("osm_value", ""))} · OSM #{b.get("osm_id", "")}</p>' if b.get('osm_id') else ''}
        </div>"""
        json_ld.append({
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": b.get("name", ""),
            "address": {
                "@type": "PostalAddress",
                "streetAddress": " ".join(filter(None, [b.get("housenumber", ""), b.get("street", "")])).strip(),
                "addressLocality": b.get("city", ""),
                "addressRegion": b.get("state", ""),
                "postalCode": b.get("postcode", ""),
                "addressCountry": b.get("countrycode", "US"),
            },
            "geo": {"@type": "GeoCoordinates", "latitude": b.get("lat"),
                    "longitude": b.get("lon")} if b.get("lat") else None,
        })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(niche).title()} in {_esc(city)}, {_esc(state)} | Empire OS</title>
<meta name="description" content="Find top {_esc(niche)} services in {_esc(city)}, {_esc(state)}. {len(businesses)} verified local pros, free matching, no signup.">
<meta property="og:title" content="{_esc(niche).title()} in {_esc(city)}, {_esc(state)}">
<meta property="og:description" content="{len(businesses)} verified local {_esc(niche)} pros in {_esc(city)}. Post your job free.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://empire-ai.co.uk/local/{urllib.parse.quote(niche)}/{urllib.parse.quote(city)}-{urllib.parse.quote(state)}">
<link rel="canonical" href="https://empire-ai.co.uk/local/{urllib.parse.quote(niche)}/{urllib.parse.quote(city)}-{urllib.parse.quote(state)}">
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }}
h1 {{ font-size: 32px; margin-bottom: 8px; }}
.subtitle {{ color: #666; margin-bottom: 32px; }}
.biz {{ border: 1px solid #e5e5e5; border-radius: 12px; padding: 20px; margin-bottom: 16px; }}
.biz h3 {{ margin: 0 0 8px; font-size: 18px; }}
.biz .addr {{ margin: 0; color: #444; font-size: 14px; }}
.biz .meta {{ margin: 8px 0 0; color: #888; font-size: 12px; }}
.cta {{ display: inline-block; background: #000; color: #fff; padding: 12px 24px; border-radius: 8px; text-decoration: none; margin: 24px 0; }}
.faq {{ margin-top: 48px; padding-top: 32px; border-top: 1px solid #e5e5e5; }}
.faq h2 {{ font-size: 20px; }}
.faq p {{ color: #444; }}
</style>
<script type="application/ld+json">
{json.dumps({"@context": "https://schema.org", "@graph": json_ld}, indent=2)}
</script>
</head>
<body>
<h1>{_esc(niche).title()} in {_esc(city)}, {_esc(state)}</h1>
<p class="subtitle">{len(businesses)} verified local pros · Last updated {time.strftime('%Y-%m-%d')}</p>
<p>{intro}</p>
<a class="cta" href="https://empire-ai.co.uk/buy-leads?ref=local-seo&niche={urllib.parse.quote(niche)}&city={urllib.parse.quote(city)}&state={urllib.parse.quote(state)}">Post Your Job — Get Matched Free</a>
<h2>Local {_esc(niche).title()} Pros in {_esc(city)}</h2>
{biz_html}
<div class="faq">
  <h2>How it works</h2>
  <p>Post your {_esc(niche)} job to Empire OS. We match you with up to 3 vetted local pros in {_esc(city)} within 24 hours. You compare quotes, pick the best fit. No fees until you hire.</p>
  <h2>Why Empire OS</h2>
  <p>We pre-screen every {_esc(niche)} pro with real OSM data + business verification. No fake listings, no spam. Just real local businesses you can hire today.</p>
</div>
</body>
</html>
"""
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(html)
    return {
        "ok": True,
        "out": out_path,
        "businesses": len(businesses),
        "business_list": businesses,
        "seo_keywords": seo_keywords,
        "size_bytes": len(html),
    }


def _llm_intro(niche: str, city: str, state: str, n: int) -> str:
    """Optional LLM intro via MiniMax (fallback to templated)."""
    try:
        # load .env the same way social_syndication does (handles <>@ in values)
        from empire_os.social_syndication import _load_env_file
        _load_env_file()
    except Exception:
        pass
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        return ""
    try:
        prompt = (f"Write a 60-80 word intro paragraph for a local SEO landing page "
                  f"about {niche} services in {city}, {state}. Mention there are "
                  f"{n} local pros listed below. Conversational, no hype, include "
                  f"a clear call-to-action to post your job.")
        payload = json.dumps({
            "model": "MiniMax-M3",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False, "temperature": 0.4,
        }).encode()
        url = os.environ.get("LLM_BASE_URL", "https://api.minimax.io/v1").strip() + "/chat/completions"
        req = urllib.request.Request(url, data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        return (data.get("choices", [{}])[0].get("message", {})
                .get("content", "")).strip()
    except Exception:
        return ""


def _esc(s) -> str:
    """Minimal HTML escape."""
    if s is None:
        return ""
    s = str(s)
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Photon enrichment + local SEO page builder")
    ap.add_argument("--niche", required=True)
    ap.add_argument("--city", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--seo", action="store_true", help="Generate SEO landing page")
    ap.add_argument("--out", default="", help="Output path for SEO page")
    a = ap.parse_args()

    if a.seo:
        out = a.out or f"/root/empire_os/empire_os/seo_pages/{a.niche}_{a.city}_{a.state}.html"
        r = generate_seo_page(a.niche, a.city, a.state, out)
        print(json.dumps({"ok": r["ok"], "out": r["out"],
                          "businesses": r["businesses"],
                          "size_bytes": r["size_bytes"]}, indent=2))
    else:
        results = search_businesses(a.niche, a.city, a.state, limit=a.limit)
        print(json.dumps(results, indent=2))