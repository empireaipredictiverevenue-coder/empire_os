#!/usr/bin/env python3
"""
Free Audit Lead Magnet API
Runs claude-seo deterministic checks and returns JSON for lead capture.
"""
import os, sys, json, subprocess, tempfile, time
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/agent_work/agrici-claude-seo-scan/claude-seo/scripts")

# Import claude-seo scripts
from fetch_page import fetch_page
from parse_html import parse_html
from pagespeed_check import run_pagespeed, CWV_THRESHOLDS

SCRIPTS_DIR = "/root/agent_work/agrici-claude-seo-scan/claude-seo/scripts"

def run_audit(url: str) -> Dict[str, Any]:
    """Run full audit pipeline on a URL."""
    result = {
        "url": url,
        "audited_at": time.time(),
        "checks": {}
    }
    
    # 1. Fetch page
    try:
        html_path = fetch_page(url, render=False)
        if html_path and os.path.exists(html_path):
            with open(html_path) as f:
                html = f.read()
            result["fetch"] = {"ok": True, "size": len(html)}
        else:
            result["fetch"] = {"ok": False, "error": "fetch failed"}
            return result
    except Exception as e:
        result["fetch"] = {"ok": False, "error": str(e)[:200]}
        return result
    
    # 2. Parse HTML for on-page SEO
    try:
        parsed = parse_html(html, url)
        result["checks"]["onpage"] = {
            "title": parsed.get("title", ""),
            "title_len": len(parsed.get("title", "")),
            "h1_count": parsed.get("h1_count", 0),
            "h2_count": parsed.get("h2_count", 0),
            "meta_desc": parsed.get("meta_description", ""),
            "meta_desc_len": len(parsed.get("meta_description", "")),
            "images_total": parsed.get("images_total", 0),
            "images_missing_alt": parsed.get("images_missing_alt", 0),
            "links_internal": parsed.get("links_internal", 0),
            "links_external": parsed.get("links_external", 0),
            "has_schema": parsed.get("has_schema", False),
            "schema_types": parsed.get("schema_types", []),
            "word_count": parsed.get("word_count", 0),
            "has_faq": parsed.get("has_faq", False),
        }
    except Exception as e:
        result["checks"]["onpage"] = {"error": str(e)[:200]}
    
    # 3. PageSpeed Insights (optional - requires API key)
    psi_key = os.environ.get("PAGESPEED_API_KEY")
    if psi_key:
        try:
            psi = run_pagespeed(url, strategy="mobile", api_key=psi_key)
            result["checks"]["psi"] = summarize_psi(psi)
        except Exception as e:
            result["checks"]["psi"] = {"error": str(e)[:200]}
    else:
        result["checks"]["psi"] = {"skipped": "no API key"}
    
    # 4. Quick technical checks via curl
    result["checks"]["tech"] = quick_tech_checks(url)
    
    # 5. Score calculation
    result["score"] = calculate_score(result["checks"])
    result["grade"] = grade_from_score(result["score"])
    
    return result

def quick_tech_checks(url: str) -> Dict[str, Any]:
    """Run quick technical checks without external APIs."""
    import requests
    checks = {}
    try:
        # Headers
        r = requests.head(url, timeout=10, allow_redirects=True)
        checks["status"] = r.status_code
        checks["redirects"] = len(r.history)
        checks["final_url"] = r.url
        checks["server"] = r.headers.get("Server", "")
        checks["content_type"] = r.headers.get("Content-Type", "")
        checks["cache_control"] = r.headers.get("Cache-Control", "")
        checks["hsts"] = "Strict-Transport-Security" in r.headers
        checks["gzip"] = "gzip" in r.headers.get("Content-Encoding", "")
        
        # SSL
        if url.startswith("https"):
            checks["ssl"] = True
        else:
            checks["ssl"] = False
        
        # robots.txt
        try:
            robots = requests.get(url.rstrip("/") + "/robots.txt", timeout=5)
            checks["robots_txt"] = robots.status_code == 200
            checks["robots_size"] = len(robots.text)
        except:
            checks["robots_txt"] = False
        
        # sitemap.xml
        try:
            sitemap = requests.get(url.rstrip("/") + "/sitemap.xml", timeout=5)
            checks["sitemap_xml"] = sitemap.status_code == 200
        except:
            checks["sitemap_xml"] = False
            
    except Exception as e:
        checks["error"] = str(e)[:200]
    return checks

def summarize_psi(psi: Dict) -> Dict:
    """Extract key metrics from PSI response."""
    out = {}
    try:
        lighthouse = psi.get("lighthouseResult", {})
        categories = lighthouse.get("categories", {})
        out["performance_score"] = int(categories.get("performance", {}).get("score", 0) * 100)
        out["accessibility_score"] = int(categories.get("accessibility", {}).get("score", 0) * 100)
        out["best_practices_score"] = int(categories.get("best-practices", {}).get("score", 0) * 100)
        out["seo_score"] = int(categories.get("seo", {}).get("score", 0) * 100)
        
        audits = lighthouse.get("audits", {})
        for metric, key in [
            ("largest_contentful_paint", "LARGEST_CONTENTFUL_PAINT_MS"),
            ("interaction_to_next_paint", "INTERACTION_TO_NEXT_PAINT"),
            ("cumulative_layout_shift", "CUMULATIVE_LAYOUT_SHIFT_SCORE"),
            ("first_contentful_paint", "FIRST_CONTENTFUL_PAINT_MS"),
        ]:
            audit = audits.get(key, {})
            if "numericValue" in audit:
                out[metric] = audit["numericValue"]
                thresh = CWV_THRESHOLDS.get(metric, {})
                if thresh:
                    out[f"{metric}_rating"] = "good" if audit["numericValue"] <= thresh["good"] else ("poor" if audit["numericValue"] >= thresh["poor"] else "needs-improvement")
    except:
        pass
    return out

def calculate_score(checks: Dict) -> int:
    """Calculate 0-100 audit score."""
    score = 0
    max_score = 0
    
    # On-page (40 pts)
    onpage = checks.get("onpage", {})
    if isinstance(onpage, dict) and "error" not in onpage:
        max_score += 40
        if onpage.get("title") and 30 <= onpage.get("title_len", 0) <= 60:
            score += 8
        if onpage.get("h1_count") == 1:
            score += 8
        if onpage.get("meta_desc") and 120 <= onpage.get("meta_desc_len", 0) <= 160:
            score += 8
        if onpage.get("images_total", 0) > 0 and onpage.get("images_missing_alt", 0) == 0:
            score += 8
        if onpage.get("has_schema"):
            score += 8
    
    # Technical (30 pts)
    tech = checks.get("tech", {})
    if isinstance(tech, dict) and "error" not in tech:
        max_score += 30
        if tech.get("status") == 200:
            score += 6
        if tech.get("ssl"):
            score += 6
        if tech.get("hsts"):
            score += 4
        if tech.get("gzip"):
            score += 4
        if tech.get("robots_txt"):
            score += 4
        if tech.get("sitemap_xml"):
            score += 6
    
    # PSI (30 pts)
    psi = checks.get("psi", {})
    if isinstance(psi, dict) and "skipped" not in psi:
        max_score += 30
        perf = psi.get("performance_score", 0)
        score += int(perf * 0.3)
    
    return int((score / max_score * 100) if max_score else 0)

def grade_from_score(score: int) -> str:
    if score >= 90: return "A"
    elif score >= 80: return "B"
    elif score >= 70: return "C"
    elif score >= 60: return "D"
    else: return "F"

# CLI for testing
if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://empire-ai.co.uk"
    print(json.dumps(run_audit(url), indent=2))
