#!/usr/bin/env python3
"""
Empire Omega OS - Lead Source Integrations
===========================================
Facebook Lead Ads, LinkedIn Lead Gen Forms, Google Lead Forms
Integrated into Empire OS v3.
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
    with open("/root/empire_os/logs/lead_sources.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    if level in ("ERROR", "WARN"):
        print(json.dumps(entry))

def get_active_configs() -> List[Dict]:
    """Get all active lead source configurations."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM lead_source_config WHERE is_active = 1
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def fetch_facebook_leads(config: Dict) -> List[Dict]:
    """Fetch leads from Facebook Lead Ads."""
    token = config.get("access_token")
    form_id = config.get("form_id")
    if not token or not form_id:
        return []
    
    # Facebook Graph API - get leads from form
    url = f"https://graph.facebook.com/v18.0/{form_id}/leads"
    params = {
        "access_token": token,
        "fields": "id,field_data,created_time,ad_id,adset_id,campaign_id",
        "limit": 100,
    }
    
    leads = []
    while True:
        query = urllib.parse.urlencode(params)
        url_full = f"{url}?{query}"
        
        try:
            req = urllib.request.Request(url_full)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            
            for lead in data.get("data", []):
                field_data = {f["name"]: f["values"][0] if f["values"] else "" for f in lead.get("field_data", [])}
                leads.append({
                    "source_lead_id": lead["id"],
                    "source": "facebook",
                    "first_name": field_data.get("first_name", ""),
                    "last_name": field_data.get("last_name", ""),
                    "email": field_data.get("email", ""),
                    "phone": field_data.get("phone_number", ""),
                    "company": field_data.get("company_name", ""),
                    "raw_data": json.dumps(lead),
                    "created_at": lead.get("created_time"),
                })
            
            # Pagination
            paging = data.get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break
            params = {}  # next URL has all params
            time.sleep(0.5)  # rate limit
            
        except Exception as e:
            log("ERROR", f"Facebook fetch failed: {e}")
            break
    
    return leads

def fetch_linkedin_leads(config: Dict) -> List[Dict]:
    """Fetch leads from LinkedIn Lead Gen Forms."""
    token = config.get("access_token")
    campaign_id = config.get("campaign_id")
    if not token or not campaign_id:
        return []
    
    url = f"https://api.linkedin.com/rest/leadGenFormResponses"
    params = {
        "campaignId": campaign_id,
        "count": 100,
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    leads = []
    try:
        query = urllib.parse.urlencode(params)
        url_full = f"{url}?{query}"
        
        req = urllib.request.Request(url_full, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        
        for lead in data.get("elements", []):
            form_data = lead.get("formData", {})
            # LinkedIn field mapping
            field_map = {
                "firstName": "first_name",
                "lastName": "last_name", 
                "email": "email",
                "phoneNumber": "phone",
                "companyName": "company",
            }
            mapped = {}
            for k, v in form_data.items():
                if k in field_map:
                    mapped[field_map[k]] = v.get("values", [""])[0] if v.get("values") else ""
            
            leads.append({
                "source_lead_id": lead.get("id", ""),
                "source": "linkedin",
                "first_name": mapped.get("first_name", ""),
                "last_name": mapped.get("last_name", ""),
                "email": mapped.get("email", ""),
                "phone": mapped.get("phone", ""),
                "company": mapped.get("company", ""),
                "raw_data": json.dumps(lead),
                "created_at": datetime.fromtimestamp(lead.get("createdAt", 0) / 1000, tz=timezone.utc).isoformat() if lead.get("createdAt") else None,
            })
    except Exception as e:
        log("ERROR", f"LinkedIn fetch failed: {e}")
    
    return leads

def fetch_google_leads(config: Dict) -> List[Dict]:
    """Fetch leads from Google Lead Forms (via Google Ads API)."""
    # Google Ads API is complex - placeholder for now
    # Would need OAuth2 + Google Ads API client
    log("INFO", "Google leads fetch - placeholder")
    return []

def normalize_lead(raw_lead: Dict) -> Dict:
    """Normalize lead from any source to standard format."""
    return {
        "source": raw_lead.get("source", ""),
        "source_lead_id": raw_lead.get("source_lead_id", ""),
        "first_name": raw_lead.get("first_name", "").strip(),
        "last_name": raw_lead.get("last_name", "").strip(),
        "email": raw_lead.get("email", "").strip().lower(),
        "phone": raw_lead.get("phone", "").strip(),
        "company": raw_lead.get("company", "").strip(),
        "raw_data": raw_lead.get("raw_data", ""),
        "created_at": raw_lead.get("created_at", datetime.now(timezone.utc).isoformat()),
    }

def save_lead(lead: Dict) -> Optional[str]:
    """Save lead to crm_leads table, return lead_id if new."""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check for duplicate by email + source
    existing = cur.execute("""
        SELECT id FROM crm_leads WHERE email = ? AND source = ?
    """, (lead["email"], lead["source"])).fetchone()
    
    if existing:
        conn.close()
        return None  # Duplicate
    
    # Insert new lead
    lead_id = f"lead_{int(time.time() * 1000)}"
    cur.execute("""
        INSERT INTO crm_leads (id, source, first_name, last_name, email, phone, company, status, raw_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
    """, (lead_id, lead["source"], lead["first_name"], lead["last_name"], 
          lead["email"], lead["phone"], lead["company"], lead["raw_data"], lead["created_at"]))
    
    conn.commit()
    conn.close()
    return lead_id

def run_discovery_cycle() -> Dict:
    """Run one complete discovery cycle across all active sources."""
    log("INFO", "Starting lead discovery cycle")
    
    configs = get_active_configs()
    if not configs:
        return {"fetched": 0, "saved": 0, "duplicates": 0, "message": "No active source configs"}
    
    total_fetched = 0
    total_saved = 0
    total_duplicates = 0
    
    # Start sync log
    conn = get_conn()
    cur = conn.cursor()
    
    for config in configs:
        config_id = config["id"]
        source = config["source"]
        
        # Start log entry
        cur.execute("""
            INSERT INTO lead_source_sync_log (config_id, status)
            VALUES (?, 'running')
        """, (config_id,))
        log_id = cur.lastrowid
        conn.commit()
        
        fetched = 0
        saved = 0
        duplicates = 0
        
        try:
            if source == "facebook":
                raw_leads = fetch_facebook_leads(config)
            elif source == "linkedin":
                raw_leads = fetch_linkedin_leads(config)
            elif source == "google":
                raw_leads = fetch_google_leads(config)
            else:
                raw_leads = []
            
            fetched = len(raw_leads)
            
            for raw in raw_leads:
                lead = normalize_lead(raw)
                lead_id = save_lead(lead)
                if lead_id:
                    saved += 1
                else:
                    duplicates += 1
            
            # Update sync log
            cur.execute("""
                UPDATE lead_source_sync_log 
                SET leads_fetched=?, leads_new=?, leads_duplicate=?, status='success', completed_at=datetime('now')
                WHERE id=?
            """, (fetched, saved, duplicates, log_id))
            
            # Update config last_sync
            cur.execute("UPDATE lead_source_config SET last_sync_at=datetime('now') WHERE id=?", (config_id,))
            conn.commit()
            
        except Exception as e:
            cur.execute("""
                UPDATE lead_source_sync_log 
                SET status='failed', error_message=?, completed_at=datetime('now')
                WHERE id=?
            """, (str(e), log_id))
            conn.commit()
            log("ERROR", f"Discovery failed for {source}", error=str(e))
        
        total_fetched += fetched
        total_saved += saved
        total_duplicates += duplicates
    
    conn.close()
    
    result = {
        "configs_processed": len(configs),
        "fetched": total_fetched,
        "saved": total_saved,
        "duplicates": total_duplicates,
    }
    log("INFO", "Discovery cycle complete", **result)
    return result

if __name__ == "__main__":
    result = run_discovery_cycle()
    print(json.dumps(result, indent=2))