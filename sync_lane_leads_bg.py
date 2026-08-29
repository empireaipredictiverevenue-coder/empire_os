#!/usr/bin/env python3
"""Background lane_leads sync - runs all remaining batches."""
import urllib.request, json, sqlite3, os, sys
import time

SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im93YmVpbmxmY2ZkdHdjd3J0dGp5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Njc3NzA3MCwiZXhwIjoyMDkyMzUzMDcwfQ.0G7wLC4Cg5ewz7iQII23J2021hrf1PN99xUYddKDQAA"
HEADERS = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Accept': 'application/json'}

def sync_batch(offset: int) -> int:
    """Sync one batch of 1000 leads."""
    url = f'https://owbeinlfcfdtwcwrttjy.supabase.co/rest/v1/lane_leads?select=*&limit=1000&offset={offset}'
    req = urllib.request.Request(url, headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Accept': 'application/json'})
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode())
    
    if not data:
        return 0
    
    con = sqlite3.connect("/root/empire_os/empire_os.db", timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.row_factory = sqlite3.Row
    
    count = 0
    for lead in data:
        lead_ref = lead.get('lead_ref') or lead.get('prospect_id') or lead.get('id')
        if not lead_ref: continue
        existing = con.execute("SELECT lead_ref FROM lane_leads WHERE lead_ref = ?", (lead_ref,)).fetchone()
        if existing:
            con.execute("UPDATE lane_leads SET lane_id=?, prospect_id=?, status=?, omega_score=?, omega_tier=?, notes=?, created_at=?, buyer_id=?, niche=?, metro=? WHERE lead_ref=?", 
                (lead.get('lane_id'), lead.get('prospect_id'), lead.get('status'), lead.get('omega_score'), lead.get('omega_tier'), lead.get('notes'), lead.get('created_at'), lead.get('buyer_id'), lead.get('niche'), lead.get('metro'), lead_ref))
        else:
            lead_ref = lead.get('lead_ref') or lead.get('prospect_id') or lead.get('id')
            con.execute("INSERT INTO lane_leads (lead_ref, lane_id, prospect_id, status, omega_score, omega_tier, notes, created_at, buyer_id, niche, metro) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (lead_ref, lead.get('lane_id'), lead.get('prospect_id'), lead.get('status'), lead.get('omega_score'), lead.get('omega_tier'), lead.get('notes'), lead.get('created_at'), lead.get('buyer_id'), lead.get('niche'), lead.get('metro')))
        count += 1
    
    con.commit()
    con.close()
    return count

def main():
    # Start from offset 14000 (we've done 0-13999)
    total_synced = 0
    for offset in range(14000, 135642, 1000):
        count = sync_batch(offset)
        total_synced += count
        if count < 1000:
            break
        print(f"Offset {offset}: synced {count} (total: {total_synced})")
        time.sleep(0.5)  # Rate limiting
    
    print(f"Total synced: {total_synced}")

if __name__ == "__main__":
    main()