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
rows = c.execute("""
    SELECT 
        id as lead_uid,
        source,
        business_name,
        contact_name,
        email,
        phone,
        metro,
        niche,
        street,
        city,
        state,
        zip,
        website,
        status,
        icp_tier,
        icp_fit_score as icp_score,
        0 as enriched,
        enrichment_score,
        created_at,
        updated_at,
        '' as sold_at,
        '' as sold_price,
        '' as buyer_id,
        icp_fit_score,
        icp_name,
        '' as eval_grade,
        '' as eval_omega,
        omega_score,
        '' as correlation_id
    FROM crm_leads
""").fetchall()

print(f"Pushing {len(rows)} crm_leads...")

for i in range(0, len(rows), 100):
    batch = []
    for r in rows[i:i+100]:
        row_dict = dict(r)
        # Clean empty strings to None for nullable fields
        for k, v in row_dict.items():
            if v == '':
                row_dict[k] = None
        batch.append(row_dict)
    
    data = json.dumps(batch).encode()
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/crm_leads", data=data, headers=headers, method="POST")
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print(f"  Batch {i//100} error: {e}")
    if i % 1000 == 0:
        print(f"  {i}/{len(rows)}")

print("crm_leads done")