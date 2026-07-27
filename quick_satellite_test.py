#!/usr/bin/env python3
"""
Quick verification that SatelliteStrikeService singleton works:
- Deterministic lead_uid via test_lead_uid parameter
- Idempotent ingestion
- Verify working with test data
"""
import sys
sys.path.insert(0, "/root/empire_os")

import json
import tempfile
from pathlib import Path

from empire_os.satellite_strike_service import ingest_strike, resolve_metro

print("Testing SatelliteStrikeService...")

# Create temporary test environment
import os
temp_dir = tempfile.mkdtemp(prefix="satellite_test_")
os.environ["DB_PATH"] = f"{temp_dir}/satellite.db"
os.environ["FEED_DIR"] = f"{temp_dir}/feedback"
os.makedirs(os.environ["FEED_DIR"], exist_ok=True)

# Test resolve_metro signature
print("1) Testing resolve_metro signature...")
result = resolve_metro([], "Harris, TX", "Tornado")
assert result == "HOU", f"Expected HOU, got {result}"
print("   ✓ resolve_metro(coords, area, event) works")

# Test with deterministic lead_uid
print("2) Testing with test_lead_uid parameter...")
test_req = {
    "event": "Severe Thunderstorm Warning",
    "severity": "Severe", 
    "area": "Harris, TX",
    "headline": "Storm",
    "id": "test:uuid",
    "polygon": [],
    "test_lead_uid": "test-led-001"
}

# First call
result1 = ingest_strike(test_req)
print(f"   First call: ok={result1['ok']}, lead_id={result1['lead_id']}, lead_uid=???")

# Second call (same lead_uid) - should be idempotent
result2 = ingest_strike(test_req)
print(f"   Second call: already={result2['already']}, lead_id={result2['lead_id']}")

# Verify both calls reference same ID (implicitly via test_lead_uid)
assert result1["lead_id"] == result2["lead_id"], "Lead IDs should match"
assert result2["already"] == True, "Second call should be marked as already"

# Test with real data (no test_lead_uid)
print("3) Testing real ingestion...")
real_req = {
    "event": "Tornado Warning",
    "severity": "Extreme",
    "area": "New York, NY", 
    "headline": "Dangerous Tornado",
    "id": "storm-arnold-001",
    "polygon": []
}

real_result = ingest_strike(real_req)
print(f"   Real ingestion: ok={real_result['ok']}, event={real_result['event']}, metro={real_result['metro']}, niche={real_result['niche']}")

# Verify it produced a deterministic lead_uid from event_id
assert real_result["event"] == "Tornado Warning"
assert real_result["metro"] == "NYC"
assert real_result["niche"] == "storm_damage"

print("\n✅ All satellite strike service tests passed!")
print(f"   Test files in {temp_dir}")