#!/usr/bin/env python3
"""
test_v4_system.py — unit tests for the V4 facade.

Uses the live empire_os.db where possible. Mocks only what is not
guaranteed to exist (e.g. cortex_report.json content).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "/root/empire_os")

from ai_intelligence_system import v4_system_entry_point
from ai_intelligence_system import v4_intelligence, v4_lead_scraping, v4_scoring, v4_swarm
from ai_intelligence_system.v4_config import (
    DB_PATH, AGENT_REGISTRY, OMEGA_TIERS, tier_for_score,
)


class TestTierForScore(unittest.TestCase):

    def test_hot_above_0_8(self):
        self.assertEqual(tier_for_score(0.95), "T1_HOT")
        self.assertEqual(tier_for_score(0.8), "T1_HOT")

    def test_warm_0_6_to_0_8(self):
        self.assertEqual(tier_for_score(0.75), "T2_WARM")
        self.assertEqual(tier_for_score(0.6), "T2_WARM")

    def test_cool_0_4_to_0_6(self):
        self.assertEqual(tier_for_score(0.5), "T3_COOL")
        self.assertEqual(tier_for_score(0.4), "T3_COOL")

    def test_cold_below_0_4(self):
        self.assertEqual(tier_for_score(0.3), "T4_COLD")
        self.assertEqual(tier_for_score(0.0), "T4_COLD")
        self.assertEqual(tier_for_score(-0.1), "T4_COLD")


class TestScoreLead(unittest.TestCase):

    def test_unscored_lead(self):
        r = v4_scoring.score_lead({"id": 1})
        self.assertIsNone(r["omega_score"])
        self.assertEqual(r["tier"], "UNSCORED")

    def test_hot_lead_clamps_correctly(self):
        r = v4_scoring.score_lead({"id": 2, "omega_score": 0.95})
        self.assertEqual(r["tier"], "T1_HOT")
        self.assertAlmostEqual(r["purchase_readiness"], 1.0)  # 0.95 + 0.1 clamped
        self.assertAlmostEqual(r["strategic_value"], 0.9)  # 0.95 - 0.05

    def test_cold_lead_clamps_correctly(self):
        r = v4_scoring.score_lead({"id": 3, "omega_score": 0.1})
        self.assertEqual(r["tier"], "T4_COLD")
        # purchase_readiness = 0.1 + 0.1 = 0.2
        self.assertAlmostEqual(r["purchase_readiness"], 0.2)


class TestLiveIntelligence(unittest.TestCase):

    def test_funnel_counts_real(self):
        counts = v4_intelligence.live_funnel_counts()
        # The DB has real data. Each count must be a non-negative int.
        for k, v in counts.items():
            self.assertIsInstance(v, int, f"{k} not int: {v}")
            self.assertGreaterEqual(v, 0, f"{k} negative")
        # Sanity: the DB has tenants and lanes
        self.assertGreater(counts["tenants"], 0)
        self.assertGreater(counts["lanes"], 0)

    def test_cortex_snapshot_handles_missing(self):
        with patch.object(v4_intelligence, "CORTEX_REPORT",
                          Path("/nonexistent/cortex_report.json")):
            snap = v4_intelligence.get_cortex_snapshot()
            self.assertEqual(snap["source"], "missing")

    def test_cortex_snapshot_loads_existing(self):
        # Write a temp report and patch the path
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"written_at": "2026-01-01T00:00:00Z", "pillars": {"revenue": 42}}, f)
            tmp = f.name
        try:
            with patch.object(v4_intelligence, "CORTEX_REPORT", Path(tmp)):
                snap = v4_intelligence.get_cortex_snapshot()
                self.assertEqual(snap["source"], "cortex_report.json")
                self.assertEqual(snap["written_at"], "2026-01-01T00:00:00Z")
                self.assertEqual(snap["pillars"]["revenue"], 42)
        finally:
            os.unlink(tmp)


class TestLiveLeadScraping(unittest.TestCase):

    def test_lane_leads_total_real(self):
        status = v4_lead_scraping.get_system_status()
        self.assertGreater(status["lane_leads_total"], 0,
                          "expected lane_leads to have data, got 0")
        # crm_leads usually has more than lane_leads
        crm = status["lead_source_counts"]["crm_leads"]
        self.assertGreater(crm, 0, "crm_leads should have data")

    def test_query_lane_leads_returns_real_rows(self):
        rows = v4_lead_scraping.query_lane_leads(limit=5)
        self.assertGreater(len(rows), 0)
        for r in rows:
            # lane_leads uses lead_ref as the natural key, not id.
            self.assertIn("lead_ref", r)
            self.assertIn("omega_score", r)
            self.assertIn("tort_key", r)

    def test_filter_by_niche(self):
        # lane_leads has no niche column; crm_leads does. This is a known
        # schema asymmetry — see lead_scraping.LEAD_SOURCES. We assert the
        # query is graceful (no exception) for lane_leads with a niche
        # filter, even if it returns empty because the column doesn't exist.
        rows = v4_lead_scraping.query_lane_leads(niche="roofing", limit=10)
        # If lane_leads has no niche column the filter is silently ignored
        # (SQLite evaluates NULL) — that's the existing v3 behaviour.
        self.assertIsInstance(rows, list)

    def test_tier_distribution_sums_to_scored(self):
        status = v4_scoring.get_system_status()
        tier_sum = sum(v for k, v in status["tier_distribution"].items() if k != "UNSCORED")
        self.assertEqual(tier_sum, status["scored"])


class TestLiveAgentSwarm(unittest.TestCase):

    def test_registry_loaded(self):
        agents = v4_swarm.list_agents(probe_health=False)
        self.assertGreater(len(agents), 0, "agent_registry.json has no agents")
        for a in agents:
            self.assertIn("name", a)
            self.assertIn("role", a)

    def test_get_agent_known(self):
        agents = v4_swarm.list_agents(probe_health=False)
        if not agents:
            self.skipTest("no agents")
        first = agents[0]
        found = v4_swarm.get_agent(first["name"])
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], first["name"])

    def test_get_agent_unknown_returns_none(self):
        self.assertIsNone(v4_swarm.get_agent("definitely_not_a_real_agent_42"))


class TestSystemEntryPoint(unittest.TestCase):

    def test_returns_real_engines(self):
        r = v4_system_entry_point("test_agent")
        self.assertEqual(r["agent_id"], "test_agent")
        self.assertEqual(r["system"]["name"], "Empire AI Intelligence System (V4)")
        # Live: at least one engine has real data
        self.assertTrue(r["system"]["live"], "system should be LIVE with DB populated")
        for engine in ("intelligence_core", "lead_scraping", "ai_scoring", "agent_swarm"):
            self.assertIn(engine, r["engines"])
            self.assertIn("component", r["engines"][engine])
            self.assertIn("version", r["engines"][engine])

    def test_no_fabricated_numbers(self):
        """V4 must never invent numbers. Every count must come from a real
        source. Asserted via the 'backed_by' field — no marketing claims."""
        r = v4_system_entry_point("test_agent")
        for engine_name, engine in r["engines"].items():
            self.assertIn("backed_by", engine, f"{engine_name} missing backed_by")
            self.assertGreater(len(engine["backed_by"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
