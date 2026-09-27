"""Tests for the AGI Closer agent."""
import json
from unittest.mock import MagicMock

import pytest
from empire_os.agi_closer import AgiCloserAgent, CloserSnapshot
from empire_os.funnel import SQLiteBackend, FunnelState, transition


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    return b


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.structured_chat.return_value = {"action": "skip", "reasoning": "Test mode"}
    return llm


@pytest.fixture
def agent(backend, mock_llm):
    return AgiCloserAgent(backend=backend, llm=mock_llm)


class TestCloserSnapshot:
    def test_defaults(self):
        s = CloserSnapshot(prospect_id="p1", niche="roofing", current_state="replied")
        assert s.prospect_id == "p1"
        assert s.notes == ""
        assert s.is_stale is False


class TestAgiCloserAgent:
    def test_observe_empty(self, agent):
        state = agent.observe()
        assert state["sent_count"] == 0
        assert state["replied_count"] == 0
        assert state["claimed_count"] == 0
        assert state["settled_count"] == 0
        assert state["snapshot_count"] == 0

    def test_observe_with_prospects(self, backend, agent):
        # Build a realistic pipeline
        transition(backend, "p1", FunnelState.DISCOVERED.value, "scout", notes="niche=roofing")
        transition(backend, "p1", FunnelState.MATCHED.value, "traffic", notes="niche=roofing")
        transition(backend, "p1", FunnelState.OUTREACH_DRAFTED.value, "sales", notes="niche=roofing")
        transition(backend, "p1", FunnelState.OUTREACH_SENT.value, "sales", notes="niche=roofing")
        transition(backend, "p2", FunnelState.REPLIED.value, "system", notes="niche=hvac")
        transition(backend, "p3", FunnelState.CLAIMED.value, "closer", notes="niche=solar")
        state = agent.observe()
        assert state["sent_count"] == 1
        assert state["replied_count"] == 1
        assert state["claimed_count"] == 1
        assert state["settled_count"] == 0
        assert state["snapshot_count"] == 3

    def test_act_never_mutates_legacy_funnel(self, backend, agent):
        transition(
            backend, "p1", FunnelState.REPLIED.value, "system",
            notes="niche=roofing",
        )
        before = agent.observe()

        for decision in (
            '{"action":"claim","prospect_id":"p1","reasoning":"interested"}',
            '{"action":"settle","prospect_id":"p1","amount_cents":250000,"reasoning":"deal done"}',
            '{"action":"follow_up","prospect_id":"p1","angle":"urgency","reasoning":"cold"}',
        ):
            result = agent.act(decision)
            assert result["action"] == "recommendation_only"
            assert result["execution_allowed"] is False
            assert result["canonical_path"] == "supabase_closer_state_machine"
            assert "event_id" not in result
            assert "amount_cents" not in result

        after = agent.observe()
        assert after["replied_count"] == before["replied_count"] == 1
        assert after["claimed_count"] == before["claimed_count"] == 0
        assert after["settled_count"] == before["settled_count"] == 0

    def test_act_parse_failure_is_still_non_executable(self, agent):
        result = agent.act("not-json")
        assert result["action"] == "recommendation_only"
        assert result["requested_action"] == "skip"
        assert result["execution_allowed"] is False

    def test_tick(self, agent):
        result = agent.tick()
        assert result["cycle"] == 1
        assert "decision_preview" in result
        assert "result" in result