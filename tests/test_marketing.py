"""
Tests for the Marketing persona.
"""

import pytest
from empire_os.funnel import SQLiteBackend, transition, FunnelState
from empire_os.marketing import (
    build_coverage_matrix,
    coverage_matrix,
    pick_highest_gap,
    draft_spec_for_niche,
    register_discovery,
    tick,
    CoverageGap,
)


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    return b


class TestCoverageMatrix:
    def test_default_matrix(self):
        matrix = build_coverage_matrix()
        assert "roofing" in matrix
        assert "hvac" in matrix
        assert matrix["roofing"] == 0
        assert len(matrix) == 8

    def test_gap_priority(self, backend):
        """Niche with 0 pages and 1 discovery should rank higher."""
        # Register a discovery for roofing in the funnel
        transition(backend, "niche:roofing", FunnelState.DISCOVERED, "marketing",
                   notes="aeo_discovery")

        gaps = coverage_matrix(backend)
        roofing = next(g for g in gaps if g.niche == "roofing")
        assert roofing.page_count == 0
        assert roofing.discovered_count == 1
        assert roofing.leverage_score > 0


class TestMarketing:
    def test_pick_highest_gap(self):
        gaps = [
            CoverageGap("roofing", 0, 1, 1.5),
            CoverageGap("hvac", 0, 0, 0.5),
            CoverageGap("electrical", 2, 0, 0.2),
        ]
        top = pick_highest_gap(gaps)
        assert top is not None
        assert top.niche == "roofing"

    def test_pick_highest_gap_empty(self):
        assert pick_highest_gap([]) is None

    def test_draft_spec(self, backend):
        draft = draft_spec_for_niche(backend, "hvac")
        assert draft.niche == "hvac"
        assert "DRAFT" in draft.target_audience
        assert draft.word_count_target == 1500

    def test_register_discovery(self, backend):
        eid = register_discovery(backend, "roofing")
        assert eid > 0

        from empire_os.funnel import get_state
        state = get_state(backend, "niche:roofing")
        assert state is not None
        assert state.current_state == "discovered"

    def test_tick(self, backend):
        result = tick(backend)
        assert result["scanned"] >= 8
        assert result["target_niche"] is not None
        assert result["drafts"] == 1
        assert len(result["registered"]) == 1

        # Running again should still work (target may shift)
        result2 = tick(backend)
        assert result2["scanned"] >= 8
