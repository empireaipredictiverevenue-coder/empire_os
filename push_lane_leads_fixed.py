import json
import sqlite3
import urllib.request

SUPABASE_URL = "https://owbeinlfcfdtwcwrttjy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im93YmVpbmxmY2ZkdHdjd3J0dGp5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Njc3NzA3MCwiZXhwIjoyMDkyMzUzMDcwfQ.0G7wLC4Cg5ewz7iQII23J2021hrf1PN99xUYddKDQAA"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

conn = sqlite3.connect("/root/empire_os/empire_os.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()
rows = c.execute("SELECT lane_id, prospect_id, status, omega_score, omega_tier, notes, created_at, buyer_id, niche, metro FROM lane_leads").fetchall()
print(f"Pushing {len(rows)} lane_leads...")

for i in range(0, len(rows), 100):
    batch = []
    for r in rows[i:i+100]:
        row_dict = dict(r)
        # Convert buyer_id empty string to None
        if row_dict.get('buyer_id') == '':
            row_dict['buyer_id'] = None
        # Convert omega_score to float
        if row_dict.get('omega_score') is not None:
            row_dict['omega_score'] = float(row_dict['omega_score'])
        batch.append(row_dict)
    
    data = json.dumps(batch).encode()
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/lane_leads", data=data, headers=headers, method="POST")
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print(f"  Batch {i//100} error: {e}")
    if i % 5000 == 0:
        print(f"  {i}/{len(rows)}")

print("lane_leads done")