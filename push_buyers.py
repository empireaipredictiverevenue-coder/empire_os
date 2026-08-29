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
        prospect_id as id,
        business_name as buyer_name,
        niche,
        '' as state_coverage,
        '' as timezone,
        8 as hours_open,
        20 as hours_close,
        payout_per_lead * 100 as base_payout,
        0.03 as fee_rate,
        '' as destination_phone,
        endpoint_url as webhook_url,
        100 as priority,
        active as is_active,
        datetime('now') as created_at,
        50 as daily_cap,
        0 as calls_today,
        0 as calls_accepted,
        0 as calls_offered,
        date('now') as last_reset,
        metro,
        payout_per_lead as payout_per_call,
        CASE WHEN active=1 THEN 'ACTIVE' ELSE 'INACTIVE' END as status,
        datetime('now') as updated_at,
        email,
        '' as contact_name,
        '' as notes,
        '' as reviewed_at,
        '' as reviewed_by,
        0 as monthly_retainer,
        0 as per_call_fee,
        '' as sub_niche,
        '' as org_id,
        0 as per_minute_rate,
        payout_per_lead as per_lead_rate,
        0 as per_schedule_rate
    FROM si_buyer_outreach
    WHERE active=1
""").fetchall()

print(f"Pushing {len(rows)} buyers...")

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
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/buyers", data=data, headers=headers, method="POST")
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print(f"  Batch {i//100} error: {e}")
    if i % 100 == 0:
        print(f"  {i}/{len(rows)}")

print("buyers done")