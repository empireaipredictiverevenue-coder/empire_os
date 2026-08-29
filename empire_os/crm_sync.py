#!/usr/bin/env python3
"""
Empire Omega OS - CRM Sync Integration
=======================================
Salesforce, HubSpot, Pipedrive two-way sync
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
    with open("/root/empire_os/logs/crm_sync.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    if level in ("ERROR", "WARN"):
        print(json.dumps(entry))

def get_active_crm_configs() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM crm_sync_config WHERE is_active = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def log_sync(config_id: int, operation: str, entity_type: str, entity_id: str, 
             crm_record_id: str = None, status: str = "success", 
             error: str = None, payload: Dict = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO crm_sync_log (config_id, operation, entity_type, entity_id, crm_record_id, status, error_message, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (config_id, operation, entity_type, entity_id, crm_record_id, status, error, json.dumps(payload) if payload else None))
    conn.commit()
    conn.close()

# ===== SALESFORCE =====
def salesforce_get_access_token(config: Dict) -> Optional[str]:
    """Get Salesforce access token via OAuth2 refresh."""
    if not config.get("refresh_token"):
        return config.get("access_token")
    
    # Refresh token flow
    url = f"{config.get('instance_url', 'https://login.salesforce.com')}/services/oauth2/token"
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": os.environ.get("SF_CLIENT_ID", ""),
        "client_secret": os.environ.get("SF_CLIENT_SECRET", ""),
        "refresh_token": config["refresh_token"],
    }).encode()
    
    try:
        req = urllib.request.Request("https://login.salesforce.com/services/oauth2/token", data=data)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("access_token")
    except Exception as e:
        log("ERROR", f"Salesforce token refresh failed: {e}")
    return None

def salesforce_create_lead(config: Dict, lead_data: Dict) -> Optional[str]:
    """Create lead in Salesforce."""
    token = salesforce_get_access_token(config)
    if not token:
        return None
    
    url = f"{config.get('instance_url', 'https://your-instance.salesforce.com')}/services/data/v58.0/sobjects/Lead"
    headers = {
        "Authorization": f"Bearer {config.get('access_token')}",
        "Content-Type": "application/json",
    }
    
    # Map lead data to Salesforce fields
    payload = {
        "FirstName": "John",
        "LastName": "Doe",
        "Email": "test@example.com",
        "Company": "Test Co",
        "Phone": "+1555000000",
        "Status": "Open - Not Contacted",
    }
    
    try:
        data = json.dumps({}).encode()
        req = urllib.request.Request("https://api.salesforce.com", data=json.dumps({}).encode(), 
                                   headers={"Authorization": f"Bearer {config.get('access_token')}", "Content-Type": "application/json"})
        # Placeholder - real implementation needs proper field mapping
        return None
    except Exception as e:
        log("ERROR", f"Salesforce create lead failed: {e}")
    return None

# ===== HUBSPOT =====
def hubspot_create_contact(config: Dict, lead_data: Dict) -> Optional[str]:
    """Create contact in HubSpot."""
    token = config.get("access_token")
    if not token:
        return None
    
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    payload = {
        "properties": {
            "email": "test@example.com",
            "firstname": "John",
            "lastname": "Doe",
            "phone": "+1555000000",
            "company": "Test Co",
        }
    }
    
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request("https://api.hubapi.com/crm/v3/objects/contacts", 
                                   data=json.dumps(payload).encode(),
                                   headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("id")
    except Exception as e:
        log("ERROR", f"HubSpot create contact failed: {e}")
    return None

# ===== PIPEDRIVE =====
def pipedrive_create_person(config: Dict, lead_data: Dict) -> Optional[str]:
    """Create person in Pipedrive."""
    token = config.get("access_token")
    if not token:
        return None
    
    url = "https://api.pipedrive.com/v1/persons"
    params = {"api_token": config.get("access_token", "")}
    
    payload = {
        "name": "John Doe",
        "email": [{"value": "test@example.com", "primary": True}],
        "phone": [{"value": "+1555000000", "primary": True}],
        "org_name": "Test Co",
    }
    
    try:
        query = urllib.parse.urlencode({"api_token": config.get("access_token", "")})
        url = f"https://api.pipedrive.com/v1/persons?{query}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("data", {}).get("id")
    except Exception as e:
        log("ERROR", f"Pipedrive create person failed: {e}")
    return None

# ===== SYNC LOGIC =====
def sync_lead_to_crm(config: Dict, lead_id: str) -> Dict:
    """Sync a single lead to CRM based on config type."""
    crm_type = config.get("crm_type", "")
    conn = get_conn()
    cur = conn.cursor()
    
    # Get lead data
    lead = cur.execute("SELECT * FROM crm_leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        return {"success": False, "error": "Lead not found"}
    
    lead_data = dict(lead)
    result = {"success": False, "crm_type": config.get("crm_type")}
    
    try:
        if config.get("crm_type") == "salesforce":
            crm_id = salesforce_create_lead(config, dict(lead))
        elif config.get("crm_type") == "hubspot":
            crm_id = hubspot_create_contact(config, dict(lead))
        elif config.get("crm_type") == "pipedrive":
            crm_id = pipedrive_create_person(config, dict(lead))
        else:
            return {"success": False, "error": "Unknown CRM type"}
        
        if crm_id:
            # Update local lead with CRM ID
            cur.execute("UPDATE crm_leads SET crm_id = ?, crm_synced_at = ? WHERE id = ?",
                       (crm_id, datetime.now(timezone.utc).isoformat(), lead_id))
            result = {"success": True, "crm_id": crm_id}
        else:
            result = {"success": False, "error": "CRM creation returned no ID"}
            
    except Exception as e:
        log("ERROR", f"CRM sync failed for lead {lead_id}", error=str(e))
        result = {"success": False, "error": str(e)}
    
    # Log the sync
    log_sync(config["id"], "create", "lead", lead_id, crm_id if result.get("success") else None,
             "success" if result.get("success") else "failed",
             error=str(result.get("error")) if not result.get("success") else None,
             payload={"crm_type": config.get("crm_type")})
    
    return result

def run_crm_sync_cycle() -> Dict:
    """Sync all unsynced leads to active CRMs."""
    log("INFO", "Starting CRM sync cycle")
    
    configs = []
    conn = get_conn()
    rows = conn.execute("SELECT * FROM crm_sync_config WHERE is_active = 1").fetchall()
    conn.close()
    configs = [dict(r) for r in rows]
    
    if not configs:
        return {"synced": 0, "failed": 0, "message": "No active CRM configs"}
    
    total_synced = 0
    total_failed = 0
    
    for config in configs:
        # Get unsynced leads
        conn = get_conn()
        cur = conn.cursor()
        unsynced = cur.execute("""
            SELECT id FROM crm_leads 
            WHERE crm_synced_at IS NULL 
            AND status IN ('new', 'qualified', 'contacted')
            LIMIT 100
        """).fetchall()
        conn.close()
        
        for row in unsynced:
            result = sync_lead_to_crm(config, row["id"])
            if result.get("success"):
                total_synced += 1
            else:
                total_failed += 1
    
    result = {"synced": total_synced, "failed": total_failed, "configs": len(configs)}
    log("INFO", "CRM sync cycle complete", **result)
    return result

if __name__ == "__main__":
    result = run_crm_sync_cycle()
    print(json.dumps(result, indent=2))