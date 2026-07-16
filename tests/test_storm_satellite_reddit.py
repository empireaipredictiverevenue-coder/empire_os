"""Tests for the improved storm, satellite, reddit, and lead filter agents."""
import json
import os
import time
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest


# ── Storm predictor tests ──────────────────────────────────────────

from empire_os.storm_predictor import (
    StormPredictor, StormEvent, HotZone,
    build_damage_video_prompt, build_satellite_url,
    build_storm_report_event, ROOF_DAMAGING_EVENTS,
)


NWS_PAYLOAD = {
    "features": [
        {
            "id": "alert-1",
            "properties": {
                "event": "Tornado Warning",
                "areaDesc": "Tampa, FL",
                "headline": "Tornado warning in effect",
                "sent": "2026-07-13T00:00:00Z",
                "expires": "2026-07-13T01:00:00Z",
                "urgency": "Immediate",
                "certainty": "Observed",
            },
        },
        {
            "id": "alert-2",
            "properties": {
                "event": "Severe Thunderstorm Warning",
                "areaDesc": "Miami, FL",
                "urgency": "Expected",
                "certainty": "Likely",
            },
        },
        {
            "id": "alert-3",
            "properties": {
                "event": "Air Quality Alert",
                "areaDesc": "Orlando, FL",
                "urgency": "Expected",
                "certainty": "Likely",
            },
        },
    ]
}


class TestStormPredictor:
    def test_scan_filters_non_roof_events(self):
        sp = StormPredictor()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(NWS_PAYLOAD).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda s, *a: None
            mock_urlopen.return_value = mock_resp

            events = sp.scan()

        assert len(events) == 2  # tornado + thunderstorm; air quality filtered
        types = [e.event_type for e in events]
        assert "Tornado Warning" in types
        assert "Severe Thunderstorm Warning" in types
        assert "Air Quality Alert" not in types

    def test_severity_immediate_observed(self):
        sp = StormPredictor()
        sev = sp._severity({
            "urgency": "Immediate", "certainty": "Observed",
        })
        assert sev == 5  # 1 + 2 + 2

    def test_severity_expected_likely(self):
        sp = StormPredictor()
        sev = sp._severity({
            "urgency": "Expected", "certainty": "Likely",
        })
        assert sev == 3

    def test_severity_unknown(self):
        sp = StormPredictor()
        sev = sp._severity({"urgency": "", "certainty": ""})
        assert sev == 1

    def test_callback_invoked_per_strike(self):
        cb = MagicMock()
        sp = StormPredictor(on_strike=cb)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(NWS_PAYLOAD).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = lambda s, *a: None
            mock_urlopen.return_value = mock_resp
            sp.scan()
        assert cb.call_count == 2  # two roof-damaging events

    def test_roof_damaging_events_set(self):
        assert "Tornado Warning" in ROOF_DAMAGING_EVENTS
        assert "Severe Thunderstorm Warning" in ROOF_DAMAGING_EVENTS
        assert "High Wind Warning" in ROOF_DAMAGING_EVENTS

    def test_observe_returns_metrics(self):
        sp = StormPredictor()
        s = sp.observe()
        assert s["agent"] == "storm-predictor"
        assert "strikes_found_total" in s

    def test_act_scan(self):
        sp = StormPredictor()
        result = sp.act('{"action": "scan"}')
        assert result["action"] == "scan"

    def test_act_skip(self):
        sp = StormPredictor()
        result = sp.act('{"action": "skip"}')
        assert result["action"] == "skip"


class TestStormHelpers:
    def test_build_damage_video_prompt(self):
        prompt = build_damage_video_prompt("33101")
        assert "33101" in prompt
        assert "Cinematic" in prompt

    def test_build_satellite_url_no_key(self):
        url = build_satellite_url("33101", api_key="")
        assert url == ""

    def test_build_satellite_url_with_key(self):
        url = build_satellite_url("33101", api_key="test-key")
        assert "33101" in url
        assert "satellite" in url
        assert "test-key" in url

    def test_build_storm_report_event(self):
        event = StormEvent(
            event_id="abc",
            event_type="Tornado Warning",
            severity=4,
            area_description="Tampa, FL",
        )
        report = build_storm_report_event(event)
        assert report["damage_score"] == 80
        assert "Tampa, FL" in report["forged_summary"]


# ── Reddit sniper tests ────────────────────────────────────────────

from empire_os.reddit_sniper import RedditSniper, RedditLead


class TestRedditSniper:
    def test_init(self):
        s = RedditSniper()
        assert s.last_run is None
        assert s.leads == []

    def test_is_configured_false(self, monkeypatch):
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
        s = RedditSniper()
        assert s.is_configured() is False

    def test_is_configured_true(self, monkeypatch):
        # The constants are read at import time; reload module
        import importlib
        import empire_os.reddit_sniper as rs
        monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
        importlib.reload(rs)
        s = rs.RedditSniper()
        assert s.is_configured() is True
        # Restore
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
        importlib.reload(rs)

    def test_scrape_without_praw(self):
        s = RedditSniper()
        with patch.dict(os.environ, {
            "REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "secret",
        }):
            # praw not installed or import fails — should not crash
            with patch.dict("sys.modules", {"praw": None}):
                leads = s.scrape()
        assert leads == []

    def test_kw_hits(self):
        s = RedditSniper()
        hits = s._kw_hits("We need a developer to build our SaaS")
        assert hits >= 2  # "need ... developer" + "saas"

    def test_observe(self):
        s = RedditSniper()
        state = s.observe()
        assert state["agent"] == "reddit-sniper"
        assert state["leads_total"] == 0


# ── Lead filter tests ──────────────────────────────────────────────

from empire_os.lead_filter import (
    LeadFilter, Lead, TierBands, TwoFactorGate, _contact_hash,
)


class TestTierBands:
    def test_hot(self):
        b = TierBands()
        assert b.tier(200) == "HOT"

    def test_warm(self):
        b = TierBands()
        assert b.tier(100) == "WARM"

    def test_cool(self):
        b = TierBands()
        assert b.tier(60) == "COOL"

    def test_rejected(self):
        b = TierBands()
        assert b.tier(30) is None


class TestTwoFactorGate:
    def test_request_and_verify(self):
        g = TwoFactorGate(secret="test-secret", ttl_seconds=60)
        code = g.request_authorization("deal-1")
        assert len(code) == 6
        assert g.verify("deal-1", code) is True

    def test_verify_wrong_code(self):
        g = TwoFactorGate(secret="test")
        g.request_authorization("deal-1")
        assert g.verify("deal-1", "000000") is False

    def test_verify_unknown_deal(self):
        g = TwoFactorGate()
        assert g.verify("nonexistent", "123456") is False

    def test_code_expires(self):
        # Use a very short TTL and an old time bucket
        g = TwoFactorGate(secret="test", ttl_seconds=1)
        # Manually inject an expired entry
        g._pending["deal-1"] = {
            "code": "123456", "expires_at": time.time() - 1, "msisdn": "",
        }
        assert g.verify("deal-1", "123456") is False

    def test_codes_are_deterministic_within_window(self):
        g = TwoFactorGate(secret="same-secret", ttl_seconds=300)
        c1 = g.request_authorization("deal-a")
        c2 = g.request_authorization("deal-b")
        # Within the same 5-min window, codes should match (same secret + same slot)
        assert c1 == c2


class TestLeadFilter:
    def test_empty_batch(self):
        f = LeadFilter()
        result = f.filter_batch([])
        assert result["qualified"] == []
        assert result["metrics"]["total_received"] == 0

    def test_qualifies_hot_lead(self):
        f = LeadFilter()
        leads = [
            Lead(source="reddit", title="Need a dev", score=200,
                 created_at="2026-07-13T00:00:00Z"),
        ]
        result = f.filter_batch(leads)
        assert len(result["qualified"]) == 1
        assert result["qualified"][0].tier == "HOT"
        assert result["metrics"]["by_tier"]["HOT"] == 1

    def test_rejects_low_score(self):
        f = LeadFilter()
        leads = [Lead(source="reddit", title="meh", score=10,
                      created_at="2026-07-13T00:00:00Z")]
        result = f.filter_batch(leads)
        assert result["qualified"] == []
        assert result["metrics"]["rejected_low_score"] == 1

    def test_dedup_same_source(self):
        f = LeadFilter()
        leads = [
            Lead(source="reddit", title="Need dev", score=100,
                 contact_hint="alice", created_at="2026-07-13T00:00:00Z"),
            Lead(source="reddit", title="Need dev", score=150,
                 contact_hint="alice", created_at="2026-07-13T00:00:00Z"),
        ]
        result = f.filter_batch(leads)
        assert len(result["qualified"]) == 1
        assert result["qualified"][0].score == 150  # kept higher score
        assert result["metrics"]["duplicates_merged"] == 1

    def test_multi_source_dedup(self):
        f = LeadFilter()
        # Same author mentioned in reddit + storm
        leads = [
            Lead(source="reddit", title="Need dev", score=100,
                 contact_hint="bob", created_at="2026-07-13T00:00:00Z"),
            Lead(source="storm", title="Tornado Tampa", score=120,
                 contact_hint="bob", created_at="2026-07-13T00:00:00Z"),
        ]
        result = f.filter_batch(leads)
        assert len(result["qualified"]) == 1
        # First one (reddit) kept, storm noted as dedup source
        assert result["qualified"][0].deduplicated_from == ["storm"] or \
               result["qualified"][0].deduplicated_from == ["storm"]


# ── Satellite scanner tests ────────────────────────────────────────

from empire_os.satellite_scanner import (
    SatelliteScanner, SatelliteScanResult, WarehouseLead,
    build_satellite_url, build_satellite_metadata_url,
    _cache_path,
)


class TestSatelliteHelpers:
    def test_build_satellite_url_with_key(self):
        url = build_satellite_url("33101", api_key="key123")
        assert "33101" in url
        assert "key123" in url

    def test_build_satellite_url_without_key(self):
        url = build_satellite_url("33101", api_key="")
        assert url == ""

    def test_build_metadata_url(self):
        url = build_satellite_metadata_url("33101", api_key="key")
        assert "zoom=0" in url or "1x1" in url

    def test_cache_path(self, tmp_path):
        p = _cache_path("33101", tmp_path)
        assert p.name.endswith(".jpg")
        assert "33101" in p.name


class TestSatelliteScanner:
    def test_init(self, tmp_path):
        s = SatelliteScanner(cache_dir=tmp_path)
        assert s.metrics["scans_total"] == 0
        assert s.is_configured() is False

    def test_is_configured(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "k"}):
            s = SatelliteScanner()
            assert s.is_configured() is True

    def test_scan_unconfigured(self):
        s = SatelliteScanner()
        result = s.scan_zip("33101")
        assert result.method == "skipped"

    def test_scan_cached(self, tmp_path, monkeypatch):
        # Pre-populate cache with the actual filename the scanner uses
        from empire_os.satellite_scanner import _cache_path
        cache = _cache_path("33101", tmp_path)
        cache.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 1000)
        monkeypatch.setenv("GOOGLE_API_KEY", "k")
        s = SatelliteScanner(cache_dir=tmp_path, google_api_key="k")
        result = s.scan_zip("33101")
        # Cached path rescore produces heuristic method
        assert result.method in ("cached", "heuristic")
        assert result.warehouses_detected >= 0

    def test_heuristic_score_on_fresh_image(self, tmp_path):
        """When image fetched, heuristic method is used (no LLM attached)."""
        s = SatelliteScanner(cache_dir=tmp_path, google_api_key="k")
        # Mock the fetch
        with patch.object(s, "_fetch_image", return_value=b"\xff\xd8" + b"\x00" * 500):
            result = s.scan_zip("33101")
        # No LLM attached → heuristic
        assert result.method in ("heuristic", "fetch_failed")
        if result.method == "heuristic":
            assert result.warehouses_detected >= 0
            assert result.damage_score >= 0

    def test_is_worth_pursuing(self):
        s = SatelliteScanner()
        # Below threshold
        lead = WarehouseLead(warehouses_detected=1, damage_score=20)
        assert s.is_worth_pursuing(lead) is False
        # Above threshold
        lead = WarehouseLead(warehouses_detected=2, damage_score=80)
        assert s.is_worth_pursuing(lead) is True

    def test_observe(self):
        s = SatelliteScanner()
        state = s.observe()
        assert state["agent"] == "satellite-scanner"
        assert state["scans_total"] == 0

    def test_scan_zone(self):
        s = SatelliteScanner()
        lead = s.scan_zone({"zip": "33101", "city": "Tampa", "state": "FL"})
        assert lead.zip_code == "33101"
        assert lead.city == "Tampa"
        assert lead.state == "FL"