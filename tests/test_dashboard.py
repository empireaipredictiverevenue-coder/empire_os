"""Tests for the dashboard module."""
import pytest
from empire_os.funnel import SQLiteBackend, FunnelState, transition
from empire_os.dashboard import build_dashboard_data, DASHBOARD_HTML


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    # Also ensure revenue schema
    from empire_os.daily_revenue import DailyRevenueSnapshotter
    rev = DailyRevenueSnapshotter(b)
    rev.ensure_schema()
    # Add some test data
    transition(b, "p1", FunnelState.DISCOVERED.value, "scout", notes="niche=roofing")
    transition(b, "p2", FunnelState.DISCOVERED.value, "scout", notes="niche=hvac")
    transition(b, "p3", FunnelState.MATCHED.value, "traffic", notes="niche=solar")
    return b


class TestDashboardData:
    def test_build_data(self, backend):
        data = build_dashboard_data(backend)
        assert data["engine"] == "Empire OS"
        assert data["funnel_total"] == 3
        assert data["funnel"]["discovered"] == 2
        assert data["funnel"]["matched"] == 1
        assert "timestamp" in data
        assert "prospects" in data
        assert len(data["prospects"]) == 3

    def test_dashboard_html(self):
        """DASHBOARD_HTML is a valid HTML string with required sections."""
        assert "<!DOCTYPE html>" in DASHBOARD_HTML
        assert "Empire OS v3" in DASHBOARD_HTML
        assert "funnel" in DASHBOARD_HTML.lower()
        assert "agi" in DASHBOARD_HTML.lower()
        assert "loadDashboard" in DASHBOARD_HTML

    def test_dashboard_has_decision_queue(self):
        """The dashboard must include the decision queue panel."""
        assert "decision-queue" in DASHBOARD_HTML
        assert "Approve" in DASHBOARD_HTML
        assert "Deny" in DASHBOARD_HTML
        assert "tickAllAgents" in DASHBOARD_HTML

    def test_dashboard_has_agi_panel(self):
        """The dashboard must show all 4 AGI agents."""
        assert "agi-scout" in DASHBOARD_HTML
        assert "agi-marketing" in DASHBOARD_HTML
        assert "agi-sales" in DASHBOARD_HTML
        assert "agi-closer" in DASHBOARD_HTML
        assert "agi-list" in DASHBOARD_HTML

    def test_data_includes_recent_activity(self, backend):
        data = build_dashboard_data(backend)
        assert "recent_activity" in data
        assert len(data["recent_activity"]) >= 3

    def test_data_includes_revenue(self, backend):
        data = build_dashboard_data(backend)
        assert "revenue_cents" in data
        assert "settlements" in data
