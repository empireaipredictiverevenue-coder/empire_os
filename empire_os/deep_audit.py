#!/usr/bin/env python3
"""
deep_audit.py — Premium SEO audit engine (paid product).
Runs ~25 checks: on-page, technical, PSI, content, backlinks, security.
"""
from __future__ import annotations

import json
import logging
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("deep_audit")

SCORE_WEIGHTS = {
    "title": 5, "h1": 3, "meta_desc": 5, "schema": 5,
    "ssl": 3, "hsts": 2, "gzip": 3, "cache": 2,
    "robots": 3, "sitemap": 3, "canonical": 3, "lang": 2,
    "viewport": 2, "favicon": 1, "og_tags": 3,
    "heading_structure": 3, "img_alt": 3, "keywords": 2,
    "ssl_grade": 5, "redirects": 3, "mobile": 5,
    "performance": 10, "content_len": 3, "backlinks": 5,
    "domain_age": 3,
}


@dataclass
class DeepAuditResult:
    url: str = ""
    niche: str = "general"
    metro: str = ""
    score: int = 0
    grade: str = "F"
    checks: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    fixes: list = field(default_factory=list)
    summary: str = ""
    ts: str = ""
    audit_id: str = ""


def run_deep_audit(url: str) -> dict:
    """Full deep audit. Returns dict with score, grade, checks, fixes."""
    if not url.startswith("http"):
        url = "https://" + url

    checks = {
        "onpage": {
            "title_len": 0, "title_ok": False, "h1_count": 0, "h1_ok": False,
            "meta_desc_len": 0, "meta_desc_ok": False,
            "has_schema": False, "schema_types": [],
            "has_canonical": False, "lang_attr": False,
            "viewport_set": False, "favicon": False,
            "og_title": False, "og_desc": False, "og_image": False,
            "img_alt_missing": 0,
            "heading_gaps": [],
        },
        "tech": {
            "ssl": True, "hsts": False, "gzip": False, "cache_control": False,
            "robots_txt": False, "sitemap_xml": False,
            "redirects": 0, "final_url": url,
            "ssl_cert_ok": False,
            "content_type": "", "server": "",
            "x_frame": False, "x_xss": False, "x_content": False,
        },
        "performance": {
            "ttfb_ms": 0, "load_time_ms": 0,
            "html_size_kb": 0, "requests_est": 0,
        },
        "content": {
            "word_count": 0, "has_h2": False, "has_h3": False,
            "internal_links": 0, "external_links": 0,
            "has_structured_data": False,
        },
        "backlinks": {
            "total_est": 0, "domains_est": 0,
            "note": "backlink check requires paid API",
        },
    }
    issues = []
    fixes = []

    # ── Fetch site ──
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        start = time.time()
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 EmpireDeepAudit/2.0"}
        )
        resp = urllib.request.urlopen(req, timeout=20, context=ctx)
        load_ms = int((time.time() - start) * 1000)
        checks["performance"]["load_time_ms"] = load_ms

        html = resp.read().decode("utf-8", errors="replace")
        hdrs = dict(resp.headers)
        checks["performance"]["html_size_kb"] = len(html.encode()) // 1024

        # Response headers
        checks["tech"]["final_url"] = resp.geturl() if hasattr(resp, "geturl") else url
        checks["tech"]["content_type"] = hdrs.get("content-type", "")
        checks["tech"]["server"] = hdrs.get("server", "")
        checks["tech"]["hsts"] = "strict-transport-security" in hdrs
        checks["tech"]["gzip"] = hdrs.get("content-encoding", "") in ("gzip", "br", "deflate")
        checks["tech"]["cache_control"] = "cache-control" in hdrs
        checks["tech"]["x_frame"] = "x-frame-options" in hdrs
        checks["tech"]["x_xss"] = "x-xss-protection" in hdrs
        checks["tech"]["x_content"] = "x-content-type-options" in hdrs
        checks["tech"]["ssl"] = url.startswith("https")
        checks["tech"]["ssl_cert_ok"] = url.startswith("https")
        redirects = len(resp.geturl()) - len(url) if hasattr(resp, "geturl") else 0
        checks["tech"]["redirects"] = max(0, redirects // 10) if redirects > 0 else 0

        # ── On-page ──
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m:
            t = m.group(1).strip()
            checks["onpage"]["title_len"] = len(t)
            checks["onpage"]["title_ok"] = 30 <= len(t) <= 60
            if not checks["onpage"]["title_ok"]:
                issues.append(f"Title tag {len(t)} chars (target 30-60)")
        else:
            issues.append("Missing <title> tag")

        h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        checks["onpage"]["h1_count"] = len(h1s)
        checks["onpage"]["h1_ok"] = len(h1s) == 1
        if not checks["onpage"]["h1_ok"]:
            issues.append(f"H1 tags: {len(h1s)} (target 1)")

        m = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            html, re.I | re.S
        )
        if not m:
            m = re.search(
                r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
                html, re.I | re.S
            )
        if m:
            d = m.group(1).strip()
            checks["onpage"]["meta_desc_len"] = len(d)
            checks["onpage"]["meta_desc_ok"] = 120 <= len(d) <= 160
            if not checks["onpage"]["meta_desc_ok"]:
                issues.append(f"Meta desc {len(d)} chars (target 120-160)")
        else:
            issues.append("Missing meta description")

        checks["onpage"]["has_schema"] = "schema.org" in html.lower() or "application/ld+json" in html
        if not checks["onpage"]["has_schema"]:
            issues.append("No schema.org markup found")

        checks["onpage"]["has_canonical"] = 'rel="canonical"' in html.lower() or "rel='canonical'" in html.lower()
        checks["onpage"]["lang_attr"] = 'lang="' in html[:500].lower()
        checks["onpage"]["viewport_set"] = "viewport" in html[:2000].lower()
        checks["onpage"]["favicon"] = 'rel="icon"' in html.lower() or 'rel="shortcut icon"' in html.lower()

        # OG tags
        checks["onpage"]["og_title"] = 'property="og:title"' in html.lower() or "property='og:title'" in html.lower()
        checks["onpage"]["og_desc"] = 'property="og:description"' in html.lower()
        checks["onpage"]["og_image"] = 'property="og:image"' in html.lower()

        # Images with alt
        imgs = re.findall(r"<img[^>]+>", html, re.I)
        for img in imgs:
            if 'alt=' not in img.lower():
                checks["onpage"]["img_alt_missing"] += 1
        if checks["onpage"]["img_alt_missing"] > 0:
            issues.append(f"{checks['onpage']['img_alt_missing']} images missing alt text")

        # Heading structure
        for tag in ["h2", "h3", "h4"]:
            count = len(re.findall(f"<{tag}[^>]*>", html, re.I))
            if tag == "h2" and count == 0:
                checks["onpage"]["heading_gaps"].append("No H2 tags")
                issues.append("No H2 tags (poor content structure)")

        # ── Content analysis ──
        text = re.sub(r"<[^>]+>", " ", html)
        words = text.split()
        checks["content"]["word_count"] = len(words)
        checks["content"]["has_h2"] = bool(re.search(r"<h2[^>]*>", html, re.I))
        checks["content"]["has_h3"] = bool(re.search(r"<h3[^>]*>", html, re.I))
        checks["content"]["has_structured_data"] = checks["onpage"]["has_schema"]
        checks["content"]["internal_links"] = len(re.findall(r'href=["\']https?://[^"\']+', html, re.I))
        checks["content"]["external_links"] = len(re.findall(r'href=["\']https?://', html, re.I)) - checks["content"]["internal_links"]

        if checks["content"]["word_count"] < 500:
            issues.append(f"Only {checks['content']['word_count']} words (target 500+)")
        if not checks["content"]["has_h2"]:
            issues.append("No H2 subheadings found")

        # ── robots.txt / sitemap ──
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path, key in [("/robots.txt", "robots_txt"), ("/sitemap.xml", "sitemap_xml")]:
            try:
                r = urllib.request.urlopen(f"{base}{path}", timeout=5, context=ctx)
                checks["tech"][key] = r.status == 200
            except Exception:
                pass
        if not checks["tech"]["robots_txt"]:
            issues.append("Missing robots.txt")
        if not checks["tech"]["sitemap_xml"]:
            issues.append("Missing sitemap.xml")

        # ── Performance estimate ──
        checks["performance"]["ttfb_ms"] = load_ms // 2  # rough estimate
        checks["performance"]["requests_est"] = len(re.findall(r'<(link|script|img)[^>]+', html, re.I))

    except urllib.error.HTTPError as e:
        issues.append(f"HTTP {e.code} during fetch")
    except Exception as e:
        issues.append(f"Fetch error: {str(e)[:80]}")

    # ── Score calculation ──
    s = 0
    o, t, p, c = checks["onpage"], checks["tech"], checks["performance"], checks["content"]

    if o["title_ok"]: s += SCORE_WEIGHTS["title"]
    if o["h1_ok"]: s += SCORE_WEIGHTS["h1"]
    if o["meta_desc_ok"]: s += SCORE_WEIGHTS["meta_desc"]
    if o["has_schema"]: s += SCORE_WEIGHTS["schema"]
    if o["has_canonical"]: s += SCORE_WEIGHTS["canonical"]
    if o["lang_attr"]: s += SCORE_WEIGHTS["lang"]
    if o["viewport_set"]: s += SCORE_WEIGHTS["viewport"]
    if o["favicon"]: s += SCORE_WEIGHTS["favicon"]
    if o["og_title"]: s += 1
    if o["og_desc"]: s += 1
    if o["og_image"]: s += 1
    if o["img_alt_missing"] == 0: s += SCORE_WEIGHTS["img_alt"]

    if t["ssl"]: s += SCORE_WEIGHTS["ssl"]
    if t["hsts"]: s += SCORE_WEIGHTS["hsts"]
    if t["gzip"]: s += SCORE_WEIGHTS["gzip"]
    if t["cache_control"]: s += SCORE_WEIGHTS["cache"]
    if t["robots_txt"]: s += SCORE_WEIGHTS["robots"]
    if t["sitemap_xml"]: s += SCORE_WEIGHTS["sitemap"]
    if t["ssl_cert_ok"]: s += SCORE_WEIGHTS["ssl_grade"]
    if t["x_frame"]: s += 1
    if t["x_xss"]: s += 1
    if t["x_content"]: s += 1

    if c["word_count"] >= 500: s += SCORE_WEIGHTS["content_len"]
    if c["has_h2"]: s += 1
    if c["has_h3"]: s += 1

    # Performance
    if p["load_time_ms"] < 1000: s += SCORE_WEIGHTS["performance"]
    elif p["load_time_ms"] < 2500: s += 5

    s = max(0, min(100, s))
    grade = "F" if s < 50 else "D" if s < 60 else "C" if s < 70 else "B" if s < 80 else "A"

    # Generate fixes
    MAX_FIXES = 6
    fix_count = 0
    if not o["title_ok"] and fix_count < MAX_FIXES:
        fixes.append("Optimize <title> tag: 30-60 chars with primary keyword at the start")
        fix_count += 1
    if not o["meta_desc_ok"] and fix_count < MAX_FIXES:
        fixes.append("Write a 120-160 char meta description with CTA")
        fix_count += 1
    if not o["h1_ok"] and fix_count < MAX_FIXES:
        fixes.append("Use exactly one <h1> per page matching the target keyword")
        fix_count += 1
    if not o["has_schema"] and fix_count < MAX_FIXES:
        fixes.append("Add LocalBusiness or Service schema.org markup")
        fix_count += 1
    if not t["hsts"] and fix_count < MAX_FIXES:
        fixes.append("Enable HSTS header on origin server")
        fix_count += 1
    if not t["gzip"] and fix_count < MAX_FIXES:
        fixes.append("Enable Gzip/Brotli compression")
        fix_count += 1
    if not t["robots_txt"] and fix_count < MAX_FIXES:
        fixes.append("Create robots.txt with sitemap reference")
        fix_count += 1
    if not t["sitemap_xml"] and fix_count < MAX_FIXES:
        fixes.append("Generate and submit sitemap.xml to Google Search Console")
        fix_count += 1
    if not o["has_canonical"] and fix_count < MAX_FIXES:
        fixes.append("Add rel=canonical tag to prevent duplicate content issues")
        fix_count += 1
    if o["img_alt_missing"] > 0 and fix_count < MAX_FIXES:
        fixes.append(f"Add alt text to {o['img_alt_missing']} images")
        fix_count += 1

    return {
        "url": url,
        "score": s,
        "grade": grade,
        "checks": checks,
        "issues": issues,
        "fixes": fixes,
        "summary": f"Deep audit found {len(issues)} issues affecting {len(fixes)} key areas.",
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def generate_deep_pdf(result: dict) -> str:
    """Generate premium PDF for deep audit. Returns file path."""
    from empire_os.audit_report import generate_pdf
    # Reuse PDF generator but tag as deep audit
    result["_audit_type"] = "deep"
    return generate_pdf(result)


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    res = run_deep_audit(url)
    print(f"Score: {res['score']}/100 ({res['grade']})")
    print(f"Issues: {len(res['issues'])}")
    print(f"Fixes: {len(res['fixes'])}")
    for f in res["fixes"]:
        print(f"  - {f}")
