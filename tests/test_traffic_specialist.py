"""
Tests for the Traffic Specialist persona.
"""

import pytest
from empire_os.funnel import SQLiteBackend, get_state, transition, FunnelState
from empire_os.traffic_specialist import (
    DiscoveredProspect,
    discover_one,
    mark_matched,
    pipeline_status,
    tick,
)


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    return b


class TestTrafficSpecialist:
    def test_discover_one(self, backend):
        prospect = DiscoveredProspect(
            prospect_id="p1",
            niche="hvac",
            source="dbpr",
            discovered_at="2026-07-12T12:00:00",
            name="Cool Air Inc",
            phone="555-111-2222",
        )
        eid = discover_one(backend, prospect)
        assert eid > 0

        state = get_state(backend, "p1")
        assert state is not None
        assert state.current_state == "discovered"

    def test_mark_matched(self, backend):
        # First discover
        transition(backend, "p1", FunnelState.DISCOVERED, "neural-scout")

        # Then match
        eid = mark_matched(backend, "p1", notes="Lead score 0.82")
        assert eid > 0

        state = get_state(backend, "p1")
        assert state.current_state == "matched"

    def test_mark_matched_no_prospect(self, backend):
        with pytest.raises(ValueError, match="not found"):
            mark_matched(backend, "nonexistent")

    def test_mark_matched_wrong_state(self, backend):
        # Discover and then match twice
        transition(backend, "p1", FunnelState.DISCOVERED, "neural-scout")
        mark_matched(backend, "p1")

        with pytest.raises(ValueError, match="not 'discovered'"):
            mark_matched(backend, "p1")

    def test_pipeline_status_empty(self, backend):
        status = pipeline_status(backend)
        assert status["total"] == 0
        assert all(v == 0 for v in status["by_state"].values())

    def test_pipeline_status_with_data(self, backend):
        transition(backend, "p1", FunnelState.DISCOVERED, "ns")
        transition(backend, "p2", FunnelState.DISCOVERED, "ns")
        transition(backend, "p1", FunnelState.MATCHED, "ts")

        status = pipeline_status(backend)
        assert status["total"] == 2
        assert status["by_state"]["discovered"] == 1
        assert status["by_state"]["matched"] == 1

    def test_tick(self, backend):
        discovered = [
            DiscoveredProspect("p1", "roofing", "web", "2026-07-12T12:00:00"),
            DiscoveredProspect("p2", "hvac", "dbpr", "2026-07-12T12:00:00"),
        ]
        results = tick(backend, discovered=discovered)
        assert results["discovered"] == 2
        assert results["matched"] == 0

        # Now match one
        results = tick(backend, matched=["p1"])
        assert results["matched"] == 1

        state = get_state(backend, "p1")
        assert state.current_state == "matched"
