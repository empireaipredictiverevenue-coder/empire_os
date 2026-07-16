"""
Tests for the funnel state machine.
"""

import pytest
from empire_os.funnel import (
    SQLiteBackend,
    FunnelState,
    transition,
    get_state,
    events_for,
    list_states,
    count_by_state,
    InvalidTransitionError,
    EmptyActorError,
    UnknownStateError,
)


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    return b


class TestFunnelBasics:
    def test_normal_flow(self, backend):
        tid = transition(backend, "p1", FunnelState.DISCOVERED, "traffic-specialist")
        assert tid > 0

        state = get_state(backend, "p1")
        assert state is not None
        assert state.current_state == FunnelState.DISCOVERED.value

        # Advance step by step
        for s in [FunnelState.MATCHED, FunnelState.OUTREACH_DRAFTED,
                  FunnelState.OUTREACH_SENT, FunnelState.REPLIED,
                  FunnelState.CLAIMED, FunnelState.SETTLED]:
            eid = transition(backend, "p1", s, "some-actor")
            assert eid > 0
            state = get_state(backend, "p1")
            assert state.current_state == s.value

    def test_backward_transition_rejected(self, backend):
        transition(backend, "p1", FunnelState.DISCOVERED, "actor")
        transition(backend, "p1", FunnelState.MATCHED, "actor")
        with pytest.raises(InvalidTransitionError, match="Backward"):
            transition(backend, "p1", FunnelState.DISCOVERED, "actor")

    def test_skip_more_than_one_rejected(self, backend):
        transition(backend, "p1", FunnelState.DISCOVERED, "actor")
        with pytest.raises(InvalidTransitionError, match="Skip-more-than-one"):
            # DISCOVERED -> OUTREACH_SENT skips MATCHED + OUTREACH_DRAFTED
            transition(backend, "p1", FunnelState.OUTREACH_SENT, "actor")

    def test_same_state_idempotent(self, backend):
        eid1 = transition(backend, "p1", FunnelState.DISCOVERED, "actor")
        eid2 = transition(backend, "p1", FunnelState.DISCOVERED, "actor")
        assert eid2 == eid1  # same event id, no new row

        events = events_for(backend, "p1")
        assert len(events) == 1  # only one row

    def test_empty_actor_rejected(self, backend):
        with pytest.raises(EmptyActorError):
            transition(backend, "p1", FunnelState.DISCOVERED, "")

        with pytest.raises(EmptyActorError):
            transition(backend, "p1", FunnelState.MATCHED, "   ")

    def test_unknown_state_rejected(self, backend):
        with pytest.raises(UnknownStateError):
            transition(backend, "p1", "nonexistent", "actor")

    def test_get_state_nonexistent(self, backend):
        state = get_state(backend, "no-such-prospect")
        assert state is None

    def test_events_for_audit_trail(self, backend):
        transition(backend, "p1", FunnelState.DISCOVERED, "ts", notes="niche=hvac")
        transition(backend, "p1", FunnelState.MATCHED, "ts", notes="engine hit")
        events = events_for(backend, "p1")
        assert len(events) == 2
        assert events[0].from_state is None
        assert events[0].to_state == FunnelState.DISCOVERED.value
        assert events[0].notes == "niche=hvac"
        assert events[1].from_state == FunnelState.DISCOVERED.value
        assert events[1].to_state == FunnelState.MATCHED.value

    def test_list_states_all(self, backend):
        transition(backend, "p1", FunnelState.DISCOVERED, "actor")
        transition(backend, "p2", FunnelState.DISCOVERED, "actor")
        transition(backend, "p1", FunnelState.MATCHED, "actor")

        all_states = list_states(backend)
        assert len(all_states) >= 2  # at least 2 prospects

        discovered = list_states(backend, state=FunnelState.DISCOVERED.value)
        matched = list_states(backend, state=FunnelState.MATCHED.value)
        assert len(discovered) == 1  # p2
        assert len(matched) == 1     # p1

    def test_count_by_state(self, backend):
        transition(backend, "p1", FunnelState.DISCOVERED, "actor")
        transition(backend, "p2", FunnelState.DISCOVERED, "actor")
        transition(backend, "p3", FunnelState.MATCHED, "actor")
        transition(backend, "p1", FunnelState.MATCHED, "actor")

        counts = count_by_state(backend)
        assert counts["discovered"] == 1  # p2 still discovered
        assert counts["matched"] == 2     # p1 and p3 at matched
        assert counts["settled"] == 0

    def test_multiple_prospects_independent(self, backend):
        transition(backend, "p1", FunnelState.DISCOVERED, "actor")
        transition(backend, "p1", FunnelState.MATCHED, "actor")
        transition(backend, "p2", FunnelState.DISCOVERED, "actor")

        assert get_state(backend, "p1").current_state == FunnelState.MATCHED.value
        assert get_state(backend, "p2").current_state == FunnelState.DISCOVERED.value

    def test_occurred_at_precision(self, backend):
        transition(backend, "p1", FunnelState.DISCOVERED, "actor")
        transition(backend, "p2", FunnelState.DISCOVERED, "actor")
        events = events_for(backend, "p1")
        assert "." in events[0].occurred_at  # microsecond dot
