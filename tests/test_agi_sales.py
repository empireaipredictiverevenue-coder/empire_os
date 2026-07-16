"""Tests for the AGI Sales agent."""
import json
from unittest.mock import MagicMock, patch

import pytest
from empire_os.agi_sales import AgiSalesAgent, DealSnapshot
from empire_os.funnel import SQLiteBackend, FunnelState, transition
from empire_os.self_heal import HealthState


@pytest.fixture
def backend():
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    return b


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.structured_chat.return_value = {
        "action": "skip", "reasoning": "Test mode",
    }
    llm.chat.return_value = "Test outreach message body."
    return llm


@pytest.fixture
def agent(backend, mock_llm):
    return AgiSalesAgent(backend=backend, llm=mock_llm)


class TestDealSnapshot:
    def test_fields(self):
        d = DealSnapshot(prospect_id="p1", niche="roofing", current_state="discovered")
        assert d.prospect_id == "p1"
        assert d.niche == "roofing"
        assert d.current_state == "discovered"
        assert d.priority == 3  # default

    def test_defaults(self):
        d = DealSnapshot(prospect_id="p1", niche="hvac", current_state="matched")
        assert d.priority == 3
        assert d.notes == ""


class TestAgiSalesAgent:
    def test_observe_empty(self, agent):
        state = agent.observe()
        assert state["discovered_count"] == 0
        assert state["matched_count"] == 0
        assert state["deal_count"] == 0
        assert "funnel_counts" in state

    def test_observe_with_leads(self, backend, agent):
        transition(backend, "p1", FunnelState.DISCOVERED.value, "scout", notes="niche=roofing")
        transition(backend, "p2", FunnelState.DISCOVERED.value, "scout", notes="niche=hvac")
        state = agent.observe()
        assert state["discovered_count"] == 2
        assert state["deal_count"] == 2

    def test_reason(self, agent):
        state = {"discovered_count": 5, "matched_count": 0, "drafted_count": 0,
                 "sent_count": 0, "deal_count": 5, "deals_preview": [],
                 "funnel_counts": {}, "cycle": 1}
        decision = agent.reason(state)
        parsed = json.loads(decision)
        assert isinstance(parsed, dict)
        assert "action" in parsed

    def test_act_skip(self, agent):
        result = agent.act('{"action": "skip", "reasoning": "Nothing to do"}')
        assert result["action"] == "skip"
        assert "Skipped" in result["summary"]

    def test_act_match(self, backend, agent):
        transition(backend, "p1", FunnelState.DISCOVERED.value, "scout", notes="niche=roofing")
        result = agent.act(
            '{"action": "match", "prospect_id": "p1", "niche": "roofing", "angle": "storm damage"}'
        )
        assert result["action"] == "match"
        assert result.get("event_id", 0) > 0
        state = backend.execute(
            "SELECT to_state FROM si_funnel_event WHERE prospect_id=? ORDER BY id DESC LIMIT 1",
            ("p1",),
        ).fetchone()
        assert state["to_state"] == "matched"

    def test_act_draft(self, backend, agent, mock_llm):
        transition(backend, "p1", FunnelState.DISCOVERED.value, "scout", notes="niche=roofing")
        transition(backend, "p1", FunnelState.MATCHED.value, "traffic", notes="niche=roofing")
        result = agent.act(
            '{"action": "draft", "prospect_id": "p1", "niche": "roofing", "angle": "roof repair"}'
        )
        assert result["action"] == "draft"
        assert result.get("draft", "") != ""
        assert "Test outreach" in result["draft"]

    def test_tick(self, agent):
        result = agent.tick()
        assert result["cycle"] == 1
        assert "decision_preview" in result
        assert "result" in result
        # Self-heal: health snapshot is included
        assert "health" in result
        assert result["health"]["consecutive_failures"] == 0

    def test_tick_recovers_from_failure(self, backend, mock_llm):
        """A tick that fails shouldn't crash the agent."""
        agent = AgiSalesAgent(backend=backend, llm=mock_llm)
        # Make observe() blow up
        agent.observe = MagicMock(side_effect=RuntimeError("DB down"))
        result = agent.tick()
        # Should return degraded status, not crash
        assert result["status"] == "degraded"
        assert "DB down" in result["error"]
        assert agent.health.consecutive_failures == 1
        assert agent.health.is_degraded is False  # only 1 failure

    def test_tick_backoff_after_failures(self, backend, mock_llm):
        """After 3 failures, agent enters backoff."""
        agent = AgiSalesAgent(backend=backend, llm=mock_llm)
        agent.observe = MagicMock(side_effect=RuntimeError("DB down"))
        # Call tick 3 times; each should fail and increment the failure counter
        for i in range(3):
            agent.tick()
        # Now in backoff
        assert agent.health.consecutive_failures >= 3
        assert agent.health.is_degraded is True

    def test_health_check(self, agent):
        h = agent.health_check()
        assert h["name"] == "agi-sales"
        assert "consecutive_failures" in h
        assert "is_degraded" in h
