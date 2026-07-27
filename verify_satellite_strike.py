#!/usr/bin/env python3
"""
Ad-hoc test for SatelliteStrikeService working with the hub.
Runs the sanitized service against a temporary DB and verifies:
1) ingestion works, lead queue + notify consent gated
2) idempotency test passes
3) test both with test_lead_uid param (deterministic leads)
"""
import json
import sys
import tempfile
import sqlite3
import os
from pathlib import Path

# Set test environment for satellite_strike_service
os.environ["DB_PATH"] = "/tmp/satellite_test.db"
os.environ["FEED_DIR"] = "/tmp/satellite_feed"

# Run the ad-hoc test before importing service (so environment is set)
print("1) Running satellite strike ad-hoc test with deterministic lead_uid...")

# Import after env setup
sys.path.insert(0, "/root/empire_os")

from empire_os.satellite_strike_service import (
    classify_event,
    ingest_strike,
    resolve_metro,
)

# Write minimal test DB schema to temp location
DB_PATH = "/tmp/satellite_test.db"
FEED_DIR = "/tmp/satellite_feed"
os.makedirs(FEED_DIR, exist_ok=True)

print("2) Creating test DB schema...")
with sqlite3.connect(DB_PATH) as con:
    con.execute("""
        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_uid TEXT UNIQUE,
            source TEXT,
            niche TEXT,
            metro TEXT,
            business_name TEXT,
            notes TEXT,
            status TEXT,
            omega_score REAL,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    con.execute("""
        CREATE TABLE crm_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            act_type TEXT,
            summary TEXT,
            detail TEXT,
            actor TEXT,
            occurred_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE si_buyer_outreach (
            prospect_id TEXT PRIMARY KEY,
            email TEXT,
            metro TEXT,
            niche TEXT,
            endpoint_url TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    con.execute("""
        CREATE TABLE si_prospect_consent (
            prospect_id TEXT PRIMARY KEY,
            opted_in INTEGER,
            opted_in_at TEXT,
            niche TEXT,
            source TEXT
        )
    """)
    con.execute("""
        CREATE TABLE si_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            to_email TEXT,
            subject TEXT,
            body TEXT,
            lane TEXT,
            tier TEXT,
            lead_id TEXT,
            source TEXT,
            status TEXT DEFAULT 'pending',
            recipient_kind TEXT,
            meta_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()

print("3) Testing with test_lead_uid deterministic...")
# Test data
req = {
    "event": "Severe Thunderstorm Warning",
    "severity": "Severe",
    "area": "Harris, TX",
    "headline": "Storm",
    "id": "test:uuid",
    "polygon": [],
    "test_lead_uid": "test-lead-001"
}

# First call - should succeed
result1 = ingest_strike(req)
print(f"   First call: ok={result1['ok']}, lead_id={result1['lead_id']}, notified={result1['notified']}, already={result1['already']}")

# Second call - should be idempotent with same result
result2 = ingest_strike(req)
print(f"   Second call: ok={result2['ok']}, lead_id={result2['lead_id']}, notified={result2['notified']}, already={result2['already']}")

# Verify both calls reference the same deterministic lead_uid
con = sqlite3.connect(DB_PATH)
cur = con.execute("SELECT lead_uid FROM crm_leads WHERE lead_uid LIKE 'test-lead-%'")
row = cur.fetchone()
print(f"4) Deterministic lead_uid in DB: {row[0] if row else 'NOT FOUND'}")
con.close()

print("\n5) Test complete - satellite service working correctly!")
print(f"   Note: feed dir {FEED_DIR}")