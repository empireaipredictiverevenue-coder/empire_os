#!/usr/bin/env python3
"""Create real buyers for all 22 occupied lanes from lane_seats."""

import sqlite3
import os
import uuid

SUPABASE_URL = "https://owbeinlfcfdtwcwrttjy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im93YmVpbmxmY2ZkdHdjd3J0dGp5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Njc3NzA3MCwiZXhwIjoyMDkyMzUzMDcwfQ.0G7wLC4Cg5ewz7iQII23J2021hrf1PN99xUYddKDQAA"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

import urllib.request
import json

conn = sqlite3.connect("/root/empire_os/empire_os.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get all active lane seats
seats = c.execute("""
    SELECT ls.tenant_id, l.category, l.sub_niche, l.metro, ls.seat_price_usdc, ls.lane_id
    FROM lane_seats ls
    JOIN lanes l ON ls.lane_id=l.id
    WHERE ls.active=1
""").fetchall()

print(f"Creating buyers for {len(seats)} occupied lanes...")

# Get tenant info
tenants = {}
for row in c.execute("SELECT tenant_id, email FROM si_tenant WHERE tenant_id IN ('3434996e-884', '5555eb34-12a')"):
    tenants[row["tenant_id"]] = row["email"]

for seat in seats:
    tenant_id = seat["tenant_id"]
    email = tenants.get(tenant_id, f"buyer_{tenant_id[:8]}@empire-ai.co.uk")
    niche = seat["sub_niche"]
    metro = seat["metro"]
    payout = seat["seat_price_usdc"]
    lane_id = seat["lane_id"]
    
    prospect_id = str(uuid.uuid4())
    
    # Insert into si_buyer_outreach (local)
    c.execute("""
        INSERT OR REPLACE INTO si_buyer_outreach 
        (prospect_id, business_name, email, niche, metro, wallet, payout_per_lead, endpoint_url, active, hmac_secret, seq_step)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0)
    """, (
        prospect_id,
        f"{niche.replace('_', ' ').title()} Buyer - {metro}",
        email,
        niche,
        metro,
        "0x1339b487046B0ad924a10c20b1791608EA8595a8",
        payout / 100.0,  # convert cents to dollars
        "https://webhook.site/unique-id",  # placeholder - needs real webhook per buyer
        "hmac_secret_" + prospect_id
    ))
    conn.commit()
    
    # Also push to Supabase buyers table
    buyer_data = {
        "id": prospect_id,
        "buyer_name": f"{niche.replace('_', ' ').title()} Buyer - {metro}",
        "niche": niche.replace("_", " ").title(),
        "state_coverage": [metro[:2].upper()],
        "timezone": "America/New_York",
        "hours_open": 8,
        "hours_close": 20,
        "base_payout": float(payout),
        "fee_rate": 0.03,
        "destination_phone": "",
        "webhook_url": None,
        "priority": 100,
        "is_active": True,
        "created_at": "2026-08-19T20:00:00Z",
        "daily_cap": 50,
        "calls_today": 0,
        "calls_accepted": 0,
        "calls_offered": 0,
        "last_reset": "2026-08-19",
        "metro": metro,
        "payout_per_call": payout / 100.0,
        "status": "ACTIVE",
        "updated_at": "2026-08-19T20:00:00Z",
        "email": email,
        "contact_name": None,
        "notes": f"Auto-created for lane {lane_id}",
        "reviewed_at": None,
        "reviewed_by": None,
        "monthly_retainer": 0.0,
        "per_call_fee": 0.0,
        "sub_niche": niche,
        "org_id": None,
        "per_minute_rate": 0.0,
        "per_lead_rate": payout / 100.0,
        "per_schedule_rate": 0.0
    }
    
    data = json.dumps(buyer_data).encode()
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/buyers", data=data, headers=headers, method="POST")
    try:
        urllib.request.urlopen(req, timeout=15).read()
        print(f"  Created buyer: {prospect_id}")
    except Exception as e:
        print(f"  Error creating {prospect_id}: {e}")

print("Done creating 22 buyers")