#!/usr/bin/env python3
"""
Empire Omega OS - ML Learning Loop
===================================
Analyzes converted leads to improve future targeting.
Integrated into Empire OS v3.
"""

import os
import sys
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import Counter

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
    with open("/root/empire_os/logs/ml_loop.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    if level in ("ERROR", "WARN"):
        print(json.dumps(entry))

def get_converted_leads(since_hours: int = 24) -> List[Dict]:
    """Get leads that converted in the last N hours."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM crm_leads 
        WHERE status IN ('converted', 'deal_closed', 'won')
        AND sold_at >= datetime('now', ?)
        ORDER BY sold_at DESC
    """, (f'-{since_hours} hours',)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def analyze_conversions(converted: List[Dict]) -> Dict:
    """Extract patterns from converted leads."""
    if not converted:
        return {"patterns": {}, "confidence": 0}
    
    # Industry analysis
    industries = [c.get("industry", "").lower() for c in converted if c.get("industry")]
    industry_counts = Counter(industries)
    
    # Location analysis
    locations = [c.get("city", "").lower() for c in converted if c.get("city")]
    location_counts = Counter(locations)
    
    # Industry-location combos
    combos = [f"{c.get('industry','').lower()}|{c.get('city','').lower()}" 
              for c in converted if c.get("industry") and c.get("city")]
    combo_counts = Counter(combos)
    
    # Average score of converted
    scores = [c.get("omega_score", 0) for c in converted if c.get("omega_score")]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    # Source analysis
    sources = [c.get("source", "") for c in converted]
    source_counts = Counter(sources)
    
    # Company size patterns
    sizes = [c.get("company_size", "") for c in converted if c.get("company_size")]
    size_counts = Counter(sizes)
    
    # Revenue patterns
    revenues = [c.get("estimated_revenue", 0) for c in converted if c.get("estimated_revenue")]
    avg_revenue = sum(revenues) / len(revenues) if revenues else 0
    
    # Time to convert
    convert_times = []
    for c in converted:
        if c.get("created_at") and c.get("sold_at"):
            try:
                created = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                converted_dt = datetime.fromisoformat(c["sold_at"].replace("Z", "+00:00"))
                hours = (converted_dt - created).total_seconds() / 3600
                convert_times.append(hours)
            except:
                pass
    avg_convert_time = sum(convert_times) / len(convert_times) if convert_times else 0
    
    return {
        "total_conversions": len(converted),
        "avg_score": round(avg_score, 1),
        "avg_convert_time_hours": round(avg_convert_time, 1),
        "avg_revenue": round(avg_revenue, 2),
        "top_industries": industry_counts.most_common(5),
        "top_locations": location_counts.most_common(5),
        "top_combos": combo_counts.most_common(5),
        "top_sources": source_counts.most_common(5),
        "company_sizes": size_counts.most_common(3),
    }

def generate_discovery_queries(insights: Dict) -> List[str]:
    """Generate search queries based on ML insights."""
    queries = []
    
    # Top industry + location combos
    for combo, count in insights.get("top_combos", [])[:3]:
        industry, location = combo.split("|", 1)
        if industry and location:
            queries.append(f"{industry} {location} B2B high-ticket service")
    
    # Top industries
    for industry, count in insights.get("top_industries", [])[:3]:
        queries.append(f"{industry} B2B high-ticket leads")
    
    # Top locations
    for location, count in insights.get("top_locations", [])[:3]:
        queries.append(f"B2B services {location} high-ticket")
    
    # Source-specific
    for source, count in insights.get("top_sources", [])[:2]:
        queries.append(f"{source} lead generation high-ticket")
    
    # Add revenue-focused queries
    if insights.get("avg_revenue", 0) > 10000:
        queries.append("high revenue B2B service companies")
    
    return list(set(queries))  # deduplicate

def update_discovery_strategy(insights: Dict) -> Dict:
    """Update lead discovery config based on ML insights."""
    queries = generate_discovery_queries(insights)
    
    # Update active discovery configs with new queries
    conn = get_conn()
    cur = conn.cursor()
    
    # Update lead_source_config with new search queries
    for source in ["facebook", "linkedin", "google"]:
        configs = cur.execute("SELECT * FROM lead_source_config WHERE source = ? AND is_active = 1", (source,)).fetchall()
        for config in configs:
            # Store queries as JSON in config
            cur.execute("""
                UPDATE lead_source_config 
                SET search_queries = ?, updated_at = datetime('now')
                WHERE id = ?
            """, (json.dumps({"queries": queries, "updated_by": "ml_loop", "confidence": len(insights.get("top_combos", [])) / 5.0}), config["id"]))
    
    conn.commit()
    conn.close()
    
    return {"queries_generated": len(queries), "queries": queries}

def run_ml_cycle() -> Dict:
    """Run the ML learning cycle."""
    log("INFO", "Starting ML learning cycle")
    
    converted = get_converted_leads(24)  # last 24 hours
    if not converted:
        log("INFO", "No recent conversions to analyze")
        return {"conversions_analyzed": 0, "message": "No recent conversions"}
    
    # Analyze patterns
    insights = analyze_conversions(converted)
    
    # Update discovery strategy
    strategy_result = update_discovery_strategy(insights)
    
    # Store ML run
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ai_learning_runs (config_id, area, input_json, output_json, status, metrics_json, completed_at)
        VALUES (?, 'ml_loop', ?, ?, 'completed', ?, datetime('now'))
    """, (1, json.dumps({"conversions_analyzed": len(converted)}), 
          json.dumps(insights), json.dumps(insights)))
    conn.commit()
    conn.close()
    
    result = {
        "conversions_analyzed": len(converted),
        "insights": insights,
        "strategy_updated": strategy_result,
    }
    log("INFO", "ML learning cycle complete", **result)
    return result

if __name__ == "__main__":
    result = run_ml_cycle()
    print(json.dumps(result, indent=2))