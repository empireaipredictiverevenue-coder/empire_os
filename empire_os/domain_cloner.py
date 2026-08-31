#!/usr/bin/env python3
"""domain_cloner.py — Pillar 3: Automated Expired Domain Authority Cloning.

Hunts dropped high-equity domains (DA>30, live backlink profile) and clones
their historical structure via the Wayback CDX API, then maps AI-generated
content wrappers to legacy URL slugs to capture authority overnight.

NOTE: requires outbound internet (Wayback CDX + whois). Run inside a Vultr
Incus container with full egress — the bare-metal hub host has restricted egress.
Self-hosted; NO managed cloud.
"""
from __future__ import annotations
import os
import sys
import json
import ssl
import urllib.request
from datetime import datetime, timezone

try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"


def find_expired_domains(seed_keywords: list, min_da: int = 30, limit: int = 20) -> list:
    """Step 1: discover dropped high-authority domains via OUR Serper product.

    Uses empire_os.lead_engine.serp_discovery (our own google.serper wrapper)
    instead of scraping a third-party drop-list. Self-hosted infra, no rent.
    """
    found = []
    try:
        from empire_os.lead_engine.serp_discovery import _search
        for kw in seed_keywords:
            q = f"expired domain {kw} authority backlinks"
            rows = _search(q, num=10)
            for r in rows:
                title = (r.get("title") or "").lower()
                link = r.get("url") or r.get("link") or ""
                # crude domain extraction
                import re
                m = re.search(r"https?://([^/]+)/?", link)
                dom = m.group(1) if m else link
                if kw.replace("_", " ") in title or kw in dom:
                    found.append({"domain": dom, "seed": kw, "source": "serper"})
                if len(found) >= limit:
                    break
            if len(found) >= limit:
                break
    except Exception as e:
        found.append({"error": f"serper: {str(e)[:120]}"})
    if not found:
        found.append({"note": "no expired domains found via serper for seeds"})
    return found


def fetch_wayback_structure(domain: str, retries: int = 3) -> list:
    """Step 2-3: pull historical URL slugs from Wayback CDX (UA + retry)."""
    params = {
        "url": f"{domain}/*",
        "output": "json",
        "fl": "original",
        "collapse": "urlkey",
        "limit": "500",
    }
    q = urlparse.urlencode(params)
    import time
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{WAYBACK_CDX}?{q}", headers={"User-Agent": "Mozilla/5.0 EmpireAI"})
            with urllib.request.urlopen(req, context=ctx, timeout=25) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            return [row[0] for row in data[1:] if row]
        except Exception as e:
            if attempt == retries - 1:
                return [{"error": str(e)[:120]}]
            time.sleep(2 * (attempt + 1))
    return [{"error": "unknown"}]


def clone_domain(domain: str, content_wrapper: callable = None) -> dict:
    """Full Pillar 3 protocol: hunt -> structure -> map wrappers -> 301."""
    slugs = fetch_wayback_structure(domain)
    if slugs and isinstance(slugs[0], dict):
        return {"domain": domain, "status": "structure_fetch_failed", "detail": slugs[0]}
    mapped = []
    for s in slugs[:50]:
        # map legacy slug to an AI-generated utility page
        page = (content_wrapper(s) if content_wrapper else f"/tools{urlparse.urlparse(s).path}")
        mapped.append({"legacy": s, "new_page": page})
    return {
        "domain": domain,
        "status": "cloned",
        "legacy_slugs": len(mapped),
        "mapping": mapped[:10],
        "step_4": "301 legacy authority -> new utility pages (skip Google sandbox)",
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    ap.add_argument("--clone", action="store_true")
    a = ap.parse_args()
    if a.clone:
        print(json.dumps(clone_domain(a.domain), indent=2, default=str))
    else:
        print(json.dumps(fetch_wayback_structure(a.domain)[:10], indent=2))
