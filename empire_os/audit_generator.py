#!/usr/bin/env python3
"""
Empire Omega OS - Audit Generation Engine
==========================================
Back-engineered from Pro-Tech audit example.
Generates personalized efficiency audit reports.
"""

import os
import sys
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"

# ============================================================
# INDUSTRY BENCHMARKS & LEAK CALCULATIONS
# ============================================================

INDUSTRY_LEAK_MULTIPLIERS = {
    "hvac": {
        "dispatch": (350000, 550000),
        "lead_scoring": (250000, 400000),
        "mobile": (150000, 250000),
        "dispatch_per_truck": (5000, 8000),
        "lead_per_truck": (3500, 5500),
        "mobile_per_truck": (2000, 3500),
    },
    "plumbing": {
        "dispatch": (300000, 500000),
        "lead_scoring": (200000, 350000),
        "mobile": (100000, 200000),
        "dispatch_per_truck": (4000, 7000),
        "lead_per_truck": (3000, 5000),
        "mobile_per_truck": (1500, 3000),
    },
    "roofing": {
        "dispatch": (250000, 450000),
        "lead_scoring": (200000, 350000),
        "mobile": (100000, 200000),
        "dispatch_per_truck": (3500, 6500),
        "lead_per_truck": (3000, 5000),
        "mobile_per_truck": (1500, 3000),
    },
    "electrical": {
        "dispatch": (200000, 400000),
        "lead_scoring": (150000, 300000),
        "mobile": (100000, 150000),
        "dispatch_per_truck": (3000, 6000),
        "lead_per_truck": (2500, 4500),
        "mobile_per_truck": (1500, 2500),
    },
    "solar": {
        "dispatch": (300000, 500000),
        "lead_scoring": (300000, 500000),
        "mobile": (150000, 250000),
        "dispatch_per_truck": (5000, 8000),
        "lead_per_truck": (5000, 8000),
        "mobile_per_truck": (2500, 4000),
    },
    "landscaping": {
        "dispatch": (150000, 300000),
        "lead_scoring": (100000, 200000),
        "mobile": (75000, 150000),
        "dispatch_per_truck": (2500, 4500),
        "lead_per_truck": (2000, 3500),
        "mobile_per_truck": (1200, 2500),
    },
    "pest_control": {
        "dispatch": (200000, 350000),
        "lead_scoring": (150000, 250000),
        "mobile": (100000, 150000),
        "dispatch_per_truck": (3000, 5000),
        "lead_per_truck": (2500, 4000),
        "mobile_per_truck": (1500, 2500),
    },
    "cleaning": {
        "dispatch": (100000, 200000),
        "lead_scoring": (75000, 150000),
        "mobile": (50000, 100000),
        "dispatch_per_truck": (2000, 3500),
        "lead_per_truck": (1500, 3000),
        "mobile_per_truck": (1000, 2000),
    },
    "construction": {
        "dispatch": (250000, 450000),
        "lead_scoring": (200000, 350000),
        "mobile": (150000, 250000),
        "dispatch_per_truck": (3500, 6500),
        "lead_per_truck": (3000, 5500),
        "mobile_per_truck": (2000, 3500),
    },
    "medical": {
        "dispatch": (150000, 300000),
        "lead_scoring": (200000, 400000),
        "mobile": (100000, 200000),
        "dispatch_per_truck": (2500, 4500),
        "lead_per_truck": (3500, 6000),
        "mobile_per_truck": (1500, 3000),
    },
    "legal": {
        "dispatch": (100000, 200000),
        "lead_scoring": (300000, 500000),
        "mobile": (75000, 150000),
        "dispatch_per_truck": (2000, 3500),
        "lead_per_truck": (5000, 8000),
        "mobile_per_truck": (1200, 2500),
    },
    "dental": {
        "dispatch": (100000, 200000),
        "lead_scoring": (200000, 400000),
        "mobile": (100000, 200000),
        "dispatch_per_truck": (2000, 3500),
        "lead_per_truck": (3500, 6000),
        "mobile_per_truck": (1500, 3000),
    },
}

# Default multipliers for unknown industries
DEFAULT_MULTIPLIERS = {
    "dispatch": (200000, 400000),
    "lead_scoring": (150000, 300000),
    "mobile": (100000, 200000),
    "dispatch_per_truck": (3000, 6000),
    "lead_per_truck": (2500, 5000),
    "mobile_per_truck": (1500, 2500),
}

# Leak templates with descriptions
LEAK_TEMPLATES = {
    "dispatch": {
        "title": "Manual Dispatch Optimization",
        "description": "Your dispatch has some optimization, but it's not AI-powered. Market leaders use machine learning to predict demand, optimize routes in real-time, and reduce technician downtime by 20-25%.",
    },
    "lead_scoring": {
        "title": "No AI Lead Scoring",
        "description": "You're not prioritizing leads by conversion probability. Your sales team spends time on low-value prospects while high-probability leads get delayed responses.",
    },
    "mobile": {
        "title": "Limited Mobile Experience",
        "description": "Your mobile experience is basic. Modern customers expect seamless mobile booking, real-time technician tracking, and instant communication. Mobile-first competitors capture 30% more leads.",
    },
    "analytics": {
        "title": "Missing Predictive Analytics",
        "description": "You're reactive, not predictive. AI-driven demand forecasting and capacity planning can increase utilization by 15-20% and reduce emergency overtime costs.",
    },
    "crm": {
        "title": "CRM Integration Gaps",
        "description": "Your CRM doesn't automatically sync with field operations. Manual data entry creates errors, delays follow-ups, and loses 15-20% of qualified leads.",
    },
    "reviews": {
        "title": "Review Management Gap",
        "description": "You're not systematically generating and managing reviews. Companies with 50+ recent reviews convert 2.5x more leads from organic search.",
    },
    "website": {
        "title": "Website Conversion Gaps",
        "description": "Your website lacks click-to-call, online booking, and live chat. Every missing conversion element costs you 2-3 qualified leads per week.",
    },
    "follow_up": {
        "title": "Automated Follow-Up Missing",
        "description": "No automated nurture sequences for leads that don't convert immediately. 50% of leads convert after 5+ touches - you're stopping at 1-2.",
    },
    "inventory": {
        "title": "Inventory & Parts Optimization",
        "description": "No AI-driven inventory forecasting. Emergency parts orders cost 3-5x more and create 2-4 hour delays per job.",
    },
    "pricing": {
        "title": "Static Pricing Model",
        "description": "Fixed pricing leaves money on the table. Dynamic pricing based on demand, capacity, and competition can increase revenue 8-15%.",
    },
    "training": {
        "title": "Technician Skill Gaps",
        "description": "No systematic skill assessment and training. Top performers generate 2-3x revenue per truck vs. average. Structured training closes this gap.",
    },
}

# ============================================================
# AUDIT GENERATION ENGINE
# ============================================================

def get_industry_multipliers(industry: str) -> Dict:
    """Get leak multipliers for industry."""
    if not industry:
        return DEFAULT_MULTIPLIERS
    industry_lower = industry.lower()
    for ind, mults in INDUSTRY_LEAK_MULTIPLIERS.items():
        if ind in industry_lower:
            return mults
    return DEFAULT_MULTIPLIERS

def calculate_leak_range(company: Dict, leak_type: str) -> tuple:
    """Calculate leak range for a specific leak type."""
    industry = company.get("industry", "")
    fleet_size = company.get("fleet_size", 0) or company.get("trucks", 0) or 0
    
    mults = get_industry_multipliers(company.get("industry", ""))
    
    # Base range
    base_min, base_max = mults.get(leak_type, (100000, 200000))
    
    # Fleet multiplier
    fleet_multiplier = 1 + (fleet_size * 0.01) if fleet_size > 0 else 1
    
    min_val = int(base_min * fleet_multiplier)
    max_val = int(base_max * fleet_multiplier)
    
    # Add per-truck component for fleet-based leaks
    if fleet_size > 0 and f"{leak_type}_per_truck" in INDUSTRY_LEAK_MULTIPLIERS.get(company.get("industry", ""), {}):
        per_truck_min, per_truck_max = mults.get(f"{leak_type}_per_truck", (0, 0))
        min_val += int(per_truck_min * fleet_size)
        max_val += int(per_truck_max * fleet_size)
    
    return (min_val, max_val)

def format_currency(val: int) -> str:
    """Format integer as currency string."""
    if val >= 1000000:
        return f"${val/1000000:.1f}M"
    elif val >= 1000:
        return f"${val/1000:.0f}K"
    return f"${val}"

def format_range(min_val: int, max_val: int) -> str:
    """Format min-max range as currency."""
    return f"{format_currency(min_val)}-{format_currency(max_val)}/year"

# ============================================================
# AUDIT GENERATION
# ============================================================

def select_leaks_for_company(company: Dict, max_leaks: int = 4) -> List[str]:
    """Select relevant leaks for a company based on profile."""
    industry = company.get("industry", "").lower()
    fleet_size = company.get("fleet_size", 0) or company.get("trucks", 0) or 0
    has_website = bool(company.get("website"))
    has_crm = bool(company.get("crm_system"))
    
    # Core leaks (always included for fleets > 5)
    core_leaks = []
    if fleet_size >= 5:
        core_leaks = ["dispatch", "lead_scoring", "mobile"]
    elif fleet_size > 0:
        core_leaks = ["dispatch", "lead_scoring"]
    else:
        core_leaks = ["lead_scoring", "website"]
    
    # Additional leaks based on profile
    additional = []
    if not has_website:
        additional.append("website")
    if not has_crm:
        additional.append("crm")
    if fleet_size >= 10:
        additional.extend(["analytics", "inventory", "pricing"])
    if fleet_size >= 20:
        additional.extend(["reviews", "follow_up", "training"])
    
    # Select top leaks
    all_leaks = core_leaks + additional[:max_leaks - len(core_leaks)]
    return all_leaks[:max_leaks]

def generate_audit_sections(company: Dict) -> List[Dict]:
    """Generate leak sections for the audit."""
    leak_types = select_leaks_for_company(company)
    sections = []
    
    for i, leak_type in enumerate(leak_types, 1):
        template = LEAK_TEMPLATES.get(leak_type, {"title": leak_type.title(), "description": "Optimization opportunity identified."})
        min_val, max_val = calculate_leak_range(company, leak_type)
        
        sections.append({
            "number": i,
            "title": template["title"],
            "range": format_range(min_val, max_val),
            "min": min_val,
            "max": max_val,
            "description": template["description"],
        })
    
    return sections

def calculate_total_leak(sections: List[Dict]) -> tuple:
    """Calculate total leak range from sections."""
    total_min = sum(s["min"] for s in sections)
    total_max = sum(s["max"] for s in sections)
    return (total_min, total_max)

def generate_audit_token(company_id: str) -> str:
    """Generate secure portal access token."""
    data = f"{company_id}:{secrets.token_urlsafe(16)}:{datetime.now().timestamp()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32].upper()

def generate_portal_url(token: str) -> str:
    """Generate portal URL with token."""
    return f"https://{token.lower()}.thepredictivecloud.com"

def generate_audit_report(company: Dict) -> Dict:
    """Generate complete audit report for a company."""
    company_id = company.get("id", f"company_{secrets.token_hex(8)}")
    
    # Generate sections
    sections = generate_audit_sections(company)
    
    # Calculate totals
    total_min, total_max = calculate_total_leak(sections)
    
    # Generate token and portal
    token = generate_audit_token(company.get("id", company_id))
    portal_url = generate_portal_url(token)
    token_expiration = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    
    # CEO info
    ceo_name = company.get("ceo_name") or company.get("contact_name") or "CEO"
    ceo_email = company.get("ceo_email") or company.get("email", "")
    
    # Build report
    report = {
        "company_id": company.get("id", company_id),
        "company_name": company.get("name", "Your Company"),
        "ceo_name": ceo_name,
        "ceo_email": ceo_email,
        "industry": company.get("industry", "Services"),
        "location": company.get("city", "") or company.get("location", ""),
        "fleet_size": company.get("fleet_size", 0) or company.get("trucks", 0),
        "date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
        "token": token,
        "portal_url": portal_url,
        "token_expiration": token_expiration,
        "sections": sections,
        "total_leak_min": total_min,
        "total_leak_max": total_max,
        "total_leak_range": format_range(total_min, total_max),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    return report

def render_audit_markdown(report: Dict) -> str:
    """Render audit report as Markdown (matching Pro-Tech format)."""
    lines = []
    
    # Header
    lines.append(f"# EFFICIENCY REPORT: {report['company_name'].upper()}")
    lines.append(f"**Prepared for:** {report['ceo_name']}, CEO")
    lines.append(f"**Date:** {report['date']}")
    lines.append("**Classification:** Confidential Business Intelligence")
    lines.append("---")
    
    # The Opportunity
    lines.append("## THE OPPORTUNITY")
    lines.append("")
    lines.append(f"Your business is leaving **{report['total_leak_range']}** on the table. ")
    lines.append("You've got good fundamentals, but you're missing the AI layer that separates market leaders from the rest.")
    lines.append("")
    lines.append("---")
    
    # Leaks
    lines.append("## WHERE THE MONEY IS LEAKING")
    lines.append("")
    
    for section in report["sections"]:
        lines.append(f"**Leak #{section['number']}: {section['title']}** ({section['range']})")
        lines.append("")
        lines.append(section["description"])
        lines.append("")
    
    # Footer
    lines.append("---")
    lines.append(f"*Report generated: {report['generated_at'][:10]}*")
    lines.append(f"*Portal: {report['portal_url']}*")
    lines.append(f"*Token: {report['token']}*")
    
    return "\n".join(lines)

def save_audit_to_db(report: Dict) -> int:
    """Save audit to database."""
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO ai_audit_reports (company_id, audit_token, portal_url, report_json, status, created_at)
        VALUES (?, ?, ?, ?, 'generated', ?)
    """, (report["company_id"], report["token"], report["portal_url"], 
          json.dumps(report), datetime.now(timezone.utc).isoformat()))
    
    audit_id = cur.lastrowid
    conn.commit()
    conn.close()
    return audit_id

def generate_audit_for_company(company: Dict) -> Dict:
    """Main entry point: generate complete audit for a company."""
    # Generate report
    report = generate_audit_report(company)
    
    # Save to DB
    audit_id = save_audit_to_db(report)
    report["audit_id"] = audit_id
    
    # Render markdown
    markdown = render_audit_markdown(report)
    report["markdown"] = markdown
    
    return report

def run_audit_generation_cycle(limit: int = 50) -> Dict:
    """Generate audits for companies that need them."""
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM crm_leads 
        WHERE omega_score >= 15 
        AND (audit_generated IS NULL OR audit_generated = 0)
        ORDER BY omega_score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    
    if not rows:
        return {"generated": 0, "message": "No companies need audits"}
    
    generated = 0
    for row in rows:
        company = dict(row)

        # Enrich with satellite + logistics recon so fleet_size reflects
        # VERIFIED (not guessed) fleet data. Optional — never blocks audit.
        try:
            from empire_os.scout_satellite_logistics import enrich_company as _recon
            rec = _recon(company)
            fleet = rec.get("fleet", {})
            # Prefer verified fleet over any stored guess; fall back to stored.
            verified_fleet = fleet.get("fleet_size_high") or company.get("fleet_size", 0)
            if verified_fleet:
                company["fleet_size"] = verified_fleet
                company["recon_tier"] = fleet.get("whale_score_adj", {}).get("tier")
                company["recon_enrichment_score"] = rec.get("enrichment_score")
        except Exception:
            pass

        report = generate_audit_for_company(company)
        
        # Mark as generated
        conn = sqlite3.connect(DB, timeout=30)
        conn.execute("UPDATE crm_leads SET audit_generated = 1, audit_token = ? WHERE id = ?",
                     (report["token"], company["id"]))
        conn.commit()
        conn.close()
        
        generated += 1
    
    return {"generated": generated, "message": f"Generated {generated} audits"}

if __name__ == "__main__":
    # Test with sample company
    test_company = {
        "id": "test_001",
        "name": "Pro-Tech Air Conditioning",
        "industry": "hvac",
        "city": "Denver",
        "fleet_size": 70,
        "ceo_name": "Michael Chen",
        "ceo_email": "michael@protech.com",
        "website": "https://protechhvac.com",
    }
    
    report = generate_audit_for_company(test_company)
    print(render_audit_markdown(report))