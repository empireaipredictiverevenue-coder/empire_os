"""Tests for the Payout, Watcher, and Fee agents."""
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from empire_os.payout import PayoutEngine, PayoutStore, PayoutRecord
from empire_os.fee_agent import FeeAgent, FeeTier, DEFAULT_TIERS
from empire_os.watcher_agent import WatcherAgent, Alert


class TestPayoutRecord:
    def test_defaults(self):
        r = PayoutRecord()
        assert r.status == "pending"
        assert r.amount_cents == 0


class TestPayoutStore:
    def test_init_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PAYOUT_STORE", str(tmp_path / "test.json"))
        s = PayoutStore()
        assert s.records == []

    def test_add_persists(self, tmp_path, monkeypatch):
        path = tmp_path / "payouts.json"
        monkeypatch.setenv("PAYOUT_STORE", str(path))
        s = PayoutStore()
        r = PayoutRecord(payout_id="abc", amount_cents=10000)
        s.add(r)
        assert path.exists()
        # Reload
        s2 = PayoutStore()
        assert len(s2.records) == 1
        assert s2.records[0]["payout_id"] == "abc"

    def test_totals(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PAYOUT_STORE", str(tmp_path / "p.json"))
        s = PayoutStore()
        s.add(PayoutRecord(payout_id="1", amount_cents=10000, status="paid"))
        s.add(PayoutRecord(payout_id="2", amount_cents=5000, status="pending"))
        s.add(PayoutRecord(payout_id="3", amount_cents=3000, status="failed"))
        assert s.total_paid_cents() == 10000
        assert s.total_pending_cents() == 5000


class TestPayoutEngine:
    def test_configured_false(self, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
        monkeypatch.delenv("PAYPAL_SECRET", raising=False)
        e = PayoutEngine()
        e.method = "stripe"
        assert e.configured() is False

    def test_configured_stripe(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
        e = PayoutEngine()
        e.method = "stripe"
        assert e.configured() is True

    def test_payout_manual_records_pending(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PAYOUT_STORE", str(tmp_path / "p.json"))
        e = PayoutEngine()
        e.method = "manual"
        record = e.payout("settle-1", "p1", 50000)
        assert record.status in ("pending", "submitted")
        assert record.amount_cents == 50000

    def test_payout_id_uniqueness(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PAYOUT_STORE", str(tmp_path / "p.json"))
        e = PayoutEngine()
        ids = set()
        for _ in range(10):
            r = e.payout("s", "p", 1000)
            ids.add(r.payout_id)
        assert len(ids) == 10  # all unique


class TestFeeAgent:
    def test_flat_fee(self):
        a = FeeAgent(flat_bps=1000)  # 10%
        result = a.calculate(10000)
        assert result["fee_cents"] == 1000
        assert result["client_cents"] == 9000
        assert result["fee_bps"] == 1000

    def test_tiered_fee_starts_at_10_percent(self):
        """Default tier 0 is 10% — competitive starting rate."""
        a = FeeAgent(tiers=DEFAULT_TIERS)
        result = a.calculate(100000)  # $1000
        assert result["fee_bps"] == 1000  # 10%
        assert result["fee_cents"] == 10000
        assert result["client_cents"] == 90000

    def test_tiered_volume_progression(self):
        a = FeeAgent(tiers=DEFAULT_TIERS)
        # First deal at 10% (no volume yet)
        a.calculate(100000)  # $1000
        # Bump past the $10k tier
        a.calculate(2000000)  # $20k cumulative
        # Now next $100 should be at 8% tier
        result = a.calculate(10000)  # $100
        assert result["fee_bps"] == 800  # 8% tier

    def test_record_returns_split(self):
        a = FeeAgent(flat_bps=1000)
        entry = a.record("settle-1", 100000)
        assert entry["gross_cents"] == 100000
        assert entry["fee_cents"] == 10000
        assert entry["client_cents"] == 90000

    def test_observe(self):
        a = FeeAgent(flat_bps=1000)
        a.record("s1", 100000)
        a.record("s2", 50000)
        obs = a.observe()
        assert obs["settlements_processed"] == 2
        assert obs["total_fee_cents"] == 15000  # 10% of 150000
        assert obs["total_client_cents"] == 135000


class TestWatcherAgent:
    def test_init(self):
        w = WatcherAgent()
        assert w.alerts == []

    def test_check_pipeline_stall(self):
        w = WatcherAgent()
        # Mock the hub to report 200 prospects in discovered
        with patch.object(w, "_http_get", return_value={"discovered": 200}):
            alerts = w.check()
        stall_alerts = [a for a in alerts if "Pipeline stall" in a.title]
        assert len(stall_alerts) >= 1
        assert any(a.severity == "warning" for a in stall_alerts)

    def test_check_conversion_low(self):
        w = WatcherAgent()
        with patch.object(w, "_http_get", return_value={"discovered": 100, "settled": 2}):
            alerts = w.check()
        conversion_alerts = [a for a in alerts if "conversion" in a.title.lower()]
        assert len(conversion_alerts) >= 1

    def test_check_no_alerts_when_healthy(self):
        w = WatcherAgent()
        with patch.object(w, "_http_get", return_value={
            "discovered": 10, "matched": 8, "outreach_drafted": 6,
            "outreach_sent": 5, "replied": 3, "claimed": 2, "settled": 2,
        }):
            alerts = w.check()
        # Should have no stall alerts
        stall = [a for a in alerts if "stall" in a.title.lower()]
        assert len(stall) == 0

    def test_observe(self):
        w = WatcherAgent()
        state = w.observe()
        assert state["agent"] == "watcher"
        assert "total_alerts" in state


class TestAlert:
    def test_defaults(self):
        a = Alert()
        assert a.severity == ""
        assert a.created_at == ""