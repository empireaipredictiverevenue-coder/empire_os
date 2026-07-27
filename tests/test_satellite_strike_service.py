import json
import sys
import tempfile
import sqlite3
import unittest
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.satellite_strike_service import (
    classify_event,
    ingest_strike,
    resolve_metro,
)


class SatelliteStrikeServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="satellite-strike-test-")
        self.db = Path(self.tmp.name) / "test.db"
        self.feedback = Path(self.tmp.name) / "events.jsonl"
        self.con = sqlite3.connect(self.db)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_resolve_metro(self):
        # Test that polygon centroid resolves to HOU (city of Houston area)
        poly = [[-95.40, 29.70], [-95.30, 29.70], [-95.30, 29.80], [-95.40, 29.80]]
        self.assertEqual(resolve_metro(poly, "", "Tornado"), "HOU")
        # Test that polygon centroid resolves to NYC (NYC area)
        poly2 = [[-74.10, 40.60], [-74.00, 40.60], [-74.00, 40.70], [-74.10, 40.70]]
        self.assertEqual(resolve_metro(poly2, "", "Tornado"), "NYC")

    def test_classify_event(self):
        self.assertEqual(classify_event("Tornado Warning"), "storm_damage")
        self.assertEqual(classify_event("Heat Warning"), "hvac")
        self.assertEqual(classify_event("Flood Warning"), "water_damage")
        self.assertEqual(classify_event("Fire Warning"), "fire_damage")
        self.assertEqual(classify_event("Earthquake"), "general_contractor")

    def test_ingest_is_idempotent_and_only_queues_consented_recipient(self):
        # Seed consenting and non-consenting buyers for HOU/storm_damage
        self.con.execute(
            "INSERT INTO si_buyer_outreach VALUES (?, ?, ?, ?, ?, 1)",
            ('consenting_id', 'yes@example.com', 'HOU', 'storm_damage', '')
        )
        self.con.execute(
            "INSERT INTO si_buyer_outreach VALUES (?, ?, ?, ?, ?, 1)",
            ('non_consent_id', 'no@example.com', 'HOU', 'storm_damage', '')
        )
        self.con.execute(
            "INSERT INTO si_prospect_consent VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)",
            ('consenting_id', 1, 'storm_damage', 'real')
        )
        self.con.execute(
            "INSERT INTO si_prospect_consent VALUES (?, ?, NULL, ?, ?)",
            ('non_consent_id', 0, 'storm_damage', 'real')
        )
        self.con.commit()

        # First ingest of a severe storm event
        event = {
            "id": "urn:test:1",
            "event": "Severe Thunderstorm Warning",
            "severity": "Severe",
            "area": "Harris, TX",
            "headline": "Storm",
            "polygon": []
        }
        first = ingest_strike(event)
        self.assertTrue(first["ok"])
        self.assertFalse(first["already"])
        self.assertIsNotNone(first["lead_id"])
        self.assertEqual(first["niche"], "storm_damage")
        self.assertEqual(first["metro"], "HOU")
        # Only one buyer should be notified (the consenting one)
        self.assertEqual(first["notified"], 1)

        # Second ingest with same ID should be idempotent
        second = ingest_strike(event)
        self.assertTrue(second["ok"])
        self.assertTrue(second["already"])
        self.assertEqual(second["lead_id"], first["lead_id"])
        self.assertEqual(second["notified"], 0)

        # DB state unchanged after the second attempt
        crm_count = self.con.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0]
        self.assertEqual(crm_count, 1)
        outbox_count = self.con.execute("SELECT COUNT(*) FROM si_outbox").fetchone()[0]
        self.assertEqual(outbox_count, 1)
        # One feedback line written per successful ingest (first only)
        if self.feedback.exists():
            self.assertEqual(self.feedback.read_text().count("\\n"), 1)
SCHEMA = """
CREATE TABLE crm_leads (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lead_uid TEXT UNIQUE, source TEXT,
 niche TEXT, metro TEXT, business_name TEXT, notes TEXT, status TEXT,
 omega_score REAL, created_at TEXT, updated_at TEXT
);
CREATE TABLE crm_activities (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, act_type TEXT,
 summary TEXT, detail TEXT, actor TEXT, occurred_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE si_buyer_outreach (
 prospect_id TEXT PRIMARY KEY, email TEXT, metro TEXT, niche TEXT,
 endpoint_url TEXT, active INTEGER DEFAULT 1
);
CREATE TABLE si_prospect_consent (
 prospect_id TEXT PRIMARY KEY, opted_in INTEGER, opted_in_at TEXT,
 niche TEXT, source TEXT
);
CREATE TABLE si_outbox (
 id INTEGER PRIMARY KEY AUTOINCREMENT, to_email TEXT, subject TEXT, body TEXT,
 lane TEXT, tier TEXT, lead_id TEXT, source TEXT, status TEXT DEFAULT 'pending',
 recipient_kind TEXT, meta_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""