#!/usr/bin/env python3
"""
Empire Omega OS - Lead Scoring (Omega Scoring)
===============================================
Scores leads 0-30 based on tech gaps, speed, conversion signals,
industry/market size, and contact capture capabilities.
Integrated into Empire OS v3 intelligence_loop.
"""

import os
import sys
import json
import sqlite3
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"

def get_conn():
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c

def log(level: str, msg: str, **fields):
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    with open("/root/empire_os/logs/omega_scoring.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    if level in ("ERROR", "WARN"):
        print(json.dumps(entry))

# ===== SCORING CRITERIA =====
# Tech Gaps (0-10 pts): missing analytics, pixels, tracking, SSL, mobile
# Speed (0-5 pts): page load time
# Conversion Signals (0-5 pts): forms, CTAs, chat, phone tracking
# Industry/Market (0-5 pts): high-ticket, market size, competition
# Contact Capture (0-5 pts): forms, chat, click-to-call, booking

SCORING_WEIGHTS = {
    "tech_gaps": 10,
    "speed": 5,
    "conversion_signals": 5,
    "industry_market": 5,
    "contact_capture": 5,
}

HIGH_TICKET_INDUSTRIES = {
    "roofing": 5, "hvac": 5, "plumbing": 5, "solar": 5,
    "mass_tort": 5, "tort": 5, "mesothelioma": 5, "legal": 4, "law": 4,
    "medical": 4, "dental": 4, "construction": 4, "electrical": 4,
    "debt_relief": 4, "debt": 4, "water_damage": 4, "water": 4,
    "landscaping": 3, "pest_control": 3, "real_estate": 3, "real estate": 3,
    "homeowner": 3, "cleaning": 2,
}

def get_conn():
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c

def log(level: str, msg: str, **fields):
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    with open("/root/empire_os/logs/omega_scoring.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    if level in ("ERROR", "WARN"):
        print(json.dumps(entry))

def get_unscored_leads(limit: int = 100) -> List[Dict]:
    """Get leads that haven't been scored yet."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM crm_leads 
        WHERE omega_score IS NULL OR omega_score = 0
        ORDER BY created_at ASC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def analyze_website(website: str) -> Dict:
    """Analyze website for tech stack, speed, conversion signals."""
    if not website:
        return {"tech_gaps": 10, "speed": 0, "conversion_signals": 0, "contact_capture": 0}
    
    # Placeholder - real implementation would:
    # 1. Fetch website HTML
    # 2. Check for: Google Analytics, FB Pixel, SSL, mobile viewport
    # 3. Measure load time
    # 4. Check for forms, chat widgets, click-to-call, booking widgets
    # 5. Use Lighthouse or similar for speed
    
    # Placeholder scores based on domain patterns
    score = {"tech_gaps": 5, "speed": 3, "conversion_signals": 3, "contact_capture": 3}
    return score

def calculate_industry_score(industry: str) -> int:
    """Score based on industry high-ticket potential."""
    if not industry:
        return 2
    industry_lower = industry.lower()
    for ind, score in HIGH_TICKET_INDUSTRIES.items():
        if ind in industry_lower:
            return score
    return 2

def calculate_market_score(location: str) -> int:
    """Score based on market size (metro population)."""
    # Placeholder - would use census data
    major_metros = ["new york", "los angeles", "chicago", "houston", "phoenix", 
                    "philadelphia", "san antonio", "san diego", "dallas", "san jose"]
    if not location:
        return 2
    loc_lower = location.lower()
    for metro in major_metros:
        if metro in loc_lower:
            return 5
    return 3

def score_lead(lead: Dict) -> Dict:
    """Calculate Omega Score (0-30) for a lead."""
    # Tech gaps + speed + conversion signals (from website analysis)
    website = lead.get("website", "") or lead.get("company_website", "")
    analysis = analyze_website(website)
    
    tech_gaps = analysis.get("tech_gaps", 5)
    speed = analysis.get("speed", 3)
    conversion_signals = analysis.get("conversion_signals", 3)
    contact_capture = analysis.get("contact_capture", 3)
    
    # Industry & market — crm_leads has no industry/location cols;
    # map niche->industry, metro->location (live sweep data 2026-08-29).
    industry = (lead.get("industry", "")
                or lead.get("niche", "")
                or lead.get("sub_niche", ""))
    location = (lead.get("location", "")
                or lead.get("metro", "")
                or lead.get("city", ""))
    industry_score = calculate_industry_score(industry)
    market_score = calculate_market_score(location)
    industry_market = min(5, (industry_score + market_score) // 2)
    
    # Weighted total
    total = (
        tech_gaps + 
        speed + 
        conversion_signals + 
        industry_market + 
        contact_capture
    )
    
    # Determine tier
    if total >= 20:
        tier = "high"
    elif total >= 15:
        tier = "qualified"
    elif total >= 10:
        tier = "monitor"
    else:
        tier = "low"
    
    return {
        "omega_score": total,
        "tier": tier,
        "breakdown": {
            "tech_gaps": tech_gaps,
            "speed": speed,
            "conversion_signals": conversion_signals,
            "industry_market": industry_market,
            "contact_capture": contact_capture,
        }
    }

def run_scoring_cycle(limit: int = 100) -> Dict:
    """Score all unscored leads."""
    log("INFO", f"Starting scoring cycle, limit={limit}")
    
    leads = get_unscored_leads(limit)
    if not leads:
        return {"scored": 0, "message": "No unscored leads"}
    
    scored = 0
    high = 0
    qualified = 0
    monitor = 0
    low = 0
    
    conn = get_conn()
    cur = conn.cursor()
    
    for lead in leads:
        scoring = score_lead(lead)
        
        cur.execute("""
            UPDATE crm_leads 
            SET omega_score = ?, omega_tier = ?, scored_at = ?, score_breakdown = ?
            WHERE lead_uid = ?
        """, (scoring["omega_score"], scoring["tier"], 
              datetime.now(timezone.utc).isoformat(), json.dumps(scoring["breakdown"]), lead["lead_uid"]))
        
        scored += 1
        if scoring["tier"] == "high":
            high += 1
        elif scoring["tier"] == "qualified":
            qualified += 1
        elif scoring["tier"] == "monitor":
            monitor += 1
        else:
            low += 1
    
    conn.commit()
    conn.close()
    
    result = {"scored": scored, "high": high, "qualified": qualified, "monitor": monitor, "low": low}
    log("INFO", "Scoring cycle complete", **result)
    return result

if __name__ == "__main__":
    result = run_scoring_cycle(100)
    print(json.dumps(result, indent=2))