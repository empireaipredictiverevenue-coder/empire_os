"""
Tests for the CEO persona.
"""

import pytest
from empire_os.funnel import SQLiteBackend, transition, FunnelState
from empire_os.ceo import build_brief, tick, Decision


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    return b


class TestCEO:
    def test_build_brief_empty(self, backend):
        brief = build_brief(backend)
        assert brief.date is not None
        assert brief.headline["prospects_in_pipeline"] == 0
        assert brief.headline["gross_cents"] == 0
        assert len(brief.decisions) >= 1  # at least the funnel_check

    def test_build_brief_with_pipeline(self, backend):
        """Prospects in pipeline should reflect funnel counts."""
        transition(backend, "p1", FunnelState.DISCOVERED, "ns")
        transition(backend, "p2", FunnelState.MATCHED, "ts")
        transition(backend, "p3", FunnelState.REPLIED, "ts")

        brief = build_brief(backend)
        assert brief.headline["prospects_in_pipeline"] == 3
        assert brief.funnel["discovered"] == 1
        assert brief.funnel["matched"] == 1
        assert brief.funnel["replied"] == 1

    def test_decision_priority_order(self, backend):
        """Decisions should be sorted by priority (lowest first)."""
        transition(backend, "p1", FunnelState.DISCOVERED, "ns")
        transition(backend, "p1", FunnelState.MATCHED, "ts")
        transition(backend, "p2", FunnelState.DISCOVERED, "ns")
        transition(backend, "p2", FunnelState.MATCHED, "ts")
        transition(backend, "p2", FunnelState.OUTREACH_DRAFTED, "operator")
        transition(backend, "p2", FunnelState.OUTREACH_SENT, "operator")
        transition(backend, "p2", FunnelState.REPLIED, "prospect")
        transition(backend, "p3", FunnelState.REPLIED, "ts")

        brief = build_brief(backend)
        priorities = [d.priority for d in brief.decisions]
        assert priorities == sorted(priorities)  # should already be sorted

        # Should have review_replied (priority 1) before ship_draft (priority 2)
        reply_decisions = [d for d in brief.decisions if d.kind == "review_replied"]
        draft_decisions = [d for d in brief.decisions if d.kind == "ship_draft"]
        assert len(reply_decisions) >= 1
        assert len(draft_decisions) >= 1
        assert all(d.priority < draft_decisions[0].priority for d in reply_decisions)

    def test_tick_no_side_effects(self, backend):
        """The CEO tick should be read-only — no new events."""
        transition(backend, "p1", FunnelState.DISCOVERED, "ns")

        from empire_os.funnel import events_for
        before = len(events_for(backend, "p1"))

        tick(backend)  # no-op write-wise

        after = len(events_for(backend, "p1"))
        assert after == before
