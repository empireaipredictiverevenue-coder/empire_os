"""Tests for the Auto-Pilot orchestrator."""
import json
from unittest.mock import MagicMock, patch

import pytest

from empire_os.auto_pilot import AutoPilot, CycleReport


class TestCycleReport:
    def test_defaults(self):
        r = CycleReport()
        assert r.cycle == 0
        assert r.matched == 0
        assert r.revenue_cents == 0


class TestAutoPilot:
    def test_init(self):
        p = AutoPilot(hub_url="http://localhost:8080")
        assert p.cycle == 0
        assert p.totals["revenue_cents"] == 0

    def test_http_get(self):
        p = AutoPilot()
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"prospects": []}).encode()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *a: None
        with patch("urllib.request.urlopen", return_value=mock_resp):
            status, data = p._http("GET", "/v1/test")
        assert status == 200
        assert data == {"prospects": []}

    def test_http_post_with_payload(self):
        p = AutoPilot()
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True}).encode()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *a: None
        with patch("urllib.request.urlopen", return_value=mock_resp):
            status, data = p._http("POST", "/v1/test", {"x": 1})
        assert status == 200
        assert data == {"ok": True}

    def test_http_handles_failure(self):
        p = AutoPilot()
        with patch("urllib.request.urlopen", side_effect=Exception("net down")):
            status, data = p._http("GET", "/v1/test")
        assert status == 0
        assert "error" in data

    def test_run_cycle_empty(self):
        """When no leads, all counters stay at 0."""
        p = AutoPilot()
        # Mock all HTTP calls to return empty data
        with patch.object(p, "_http", return_value=(200, {"prospects": []})):
            report = p.run_cycle()
        assert report.cycle == 1
        assert report.matched == 0
        assert report.settled == 0
        assert report.revenue_cents == 0

    def test_run_cycle_increments_totals(self):
        p = AutoPilot()
        # Mock HTTP to return empty data — totals just accumulate zeros
        empty = (200, {"prospects": []})
        with patch.object(p, "_http", return_value=empty):
            report = p.run_cycle()
        # Cycle incremented
        assert report.cycle == 1
        assert p.cycle == 1
        # Totals exist
        assert p.totals["matched"] == 0

    def test_run_cycle_recovers_from_error(self):
        """One bad call shouldn't crash the whole cycle."""
        p = AutoPilot()
        call_count = [0]

        def mock_http(method, path, payload=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first call explodes")
            return (200, {"prospects": []})

        with patch.object(p, "_http", side_effect=mock_http):
            report = p.run_cycle()
        assert report.error != ""

    def test_history_appended(self):
        p = AutoPilot()
        with patch.object(p, "_http", return_value=(200, {"prospects": []})):
            p.run_cycle()
            p.run_cycle()
        assert len(p.history) == 2
        assert p.history[0]["cycle"] == 1
        assert p.history[1]["cycle"] == 2