#!/usr/bin/env python3
"""Fixed Supabase sync - UPSERT not DELETE, uses real creds from secrets"""
import os, sys, sqlite3, urllib.request, json, time
from pathlib import Path

secrets_path = Path("/root/empire_secrets/supabase.env")
if secrets_path.exists():
    env_content = secrets_path.read_text()
    import re
    url_match = re.search(r'SUPABASE_URL=(.*)', env_content)
    key_match = re.search(r'SUPABASE_SERVICE_KEY=(.*)', env_content)
    if url_match and key_match:
        SUPABASE_URL = url_match.group(1).strip()
        SUPABASE_KEY = key_match.group(1).strip()
    else:
        print("ERROR: Credentials not found in supabase.env")
        sys.exit(1)
else:
    print("ERROR: /root/empire_secrets/supabase.env not found")
    sys.exit(1)

LOCAL_DB = "/root/empire_os/empire_os.db"
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

def supabase_request(method, endpoint, data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers=HEADERS, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()) if r.read() else []

def sync_crm_leads():
    """UPSERT crm_leads from local to Supabase"""
    con = sqlite3.connect(LOCAL_DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    cur = con.cursor()
    
    cur.execute("SELECT * FROM crm_leads WHERE source != 'supabase_prospects' ORDER BY lead_uid LIMIT 500")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    con.close()
    
    if not rows:
        print("No local leads to sync")
        return 0
    
    synced = 0
    for row in rows:
        lead = dict(zip(cols, row))
        lead['synced_at'] = int(time.time())
        
        try:
            # UPSERT on lead_uid
            result = supabase_request("POST", f"crm_leads?on_conflict=lead_uid", [lead])
            synced += 1
            print(f"Synced: {lead.get('business_name', 'N/A')[:50]}")
        except Exception as e:
            print(f"Failed {lead.get('business_name', 'N/A')[:50]}: {e}")
    
    return synced

if __name__ == "__main__":
    print("=== FIXED SUPABASE SYNC (UPSERT on lead_uid) ===")
    synced = sync_crm_leads()
    print(f"Synced {synced} leads to Supabase")
