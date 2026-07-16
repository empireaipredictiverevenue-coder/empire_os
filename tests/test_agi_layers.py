"""Tests for the AGI wrapper, synthetic intelligence, and ASI meta-reasoning."""
import json
from unittest.mock import MagicMock, patch

import pytest


# ── Synthetic Intelligence ─────────────────────────────────────────

from empire_os.synthetic_intelligence import (
    SyntheticIntelligence, SyntheticExample,
)


class TestSyntheticIntelligence:
    def test_init(self):
        llm = MagicMock()
        s = SyntheticIntelligence(llm, n_synthetic=3)
        assert s.n_synthetic == 3
        assert s.examples == []

    def test_augment_parses_list(self):
        llm = MagicMock()
        llm.structured_chat.return_value = [
            {"input": {"x": 1}, "expected_output": {"y": 2}, "rationale": "test"},
            {"input": {"x": 3}, "expected_output": {"y": 4}, "rationale": "test2"},
        ]
        s = SyntheticIntelligence(llm, n_synthetic=5)
        examples = s.augment({"state": "x"}, {"decision": "y"})
        assert len(examples) == 2

    def test_augment_parses_dict_with_examples_key(self):
        llm = MagicMock()
        llm.structured_chat.return_value = {
            "examples": [{"input": {}, "expected_output": {}, "rationale": ""}]
        }
        s = SyntheticIntelligence(llm)
        examples = s.augment({}, {})
        assert len(examples) == 1

    def test_augment_handles_llm_failure(self):
        llm = MagicMock()
        llm.structured_chat.side_effect = RuntimeError("LLM down")
        s = SyntheticIntelligence(llm)
        examples = s.augment({}, {})
        assert examples == []

    def test_augment_caps_at_n_synthetic(self):
        llm = MagicMock()
        llm.structured_chat.return_value = [
            {"input": {}, "expected_output": {}, "rationale": f"r{i}"}
            for i in range(20)
        ]
        s = SyntheticIntelligence(llm, n_synthetic=3)
        examples = s.augment({}, {})
        assert len(examples) == 3

    def test_observe(self):
        s = SyntheticIntelligence(MagicMock())
        state = s.observe()
        assert state["agent"] == "synthetic-intelligence"


# ── ASI Meta-Reasoning ────────────────────────────────────────────

from empire_os.asi import ASILayer, DecisionRecord


class TestASILayer:
    def test_init(self):
        a = ASILayer(MagicMock(), window=10)
        assert a.history.maxlen == 10

    def test_record_success(self):
        a = ASILayer(MagicMock())
        a.record(1, {"d": "x"}, {"o": "y"}, success=True)
        assert a.metrics["successes"] == 1
        assert a.metrics["decisions_tracked"] == 1

    def test_record_failure(self):
        a = ASILayer(MagicMock())
        a.record(1, {}, {}, success=False)
        assert a.metrics["failures"] == 1

    def test_record_unknown(self):
        a = ASILayer(MagicMock())
        a.record(1, {}, {}, success=None)
        assert a.metrics["decisions_tracked"] == 1
        assert a.metrics["successes"] == 0
        assert a.metrics["failures"] == 0

    def test_reflect_skips_with_little_history(self):
        a = ASILayer(MagicMock())
        strategies = a.reflect()
        assert strategies == []

    def test_reflect_produces_strategies(self):
        llm = MagicMock()
        llm.structured_chat.return_value = {
            "insights": ["x"], "strategies": ["s1", "s2"]
        }
        a = ASILayer(llm, window=10)
        for i in range(3):
            a.record(i, {"d": i}, {"o": i}, success=True)
        strategies = a.reflect()
        assert len(strategies) == 2
        assert a.metrics["strategies_evolved"] == 2

    def test_observe(self):
        a = ASILayer(MagicMock())
        state = a.observe()
        assert state["agent"] == "asi-meta-reasoning"

    def test_history_capped_to_window(self):
        a = ASILayer(MagicMock(), window=3)
        for i in range(10):
            a.record(i, {}, {})
        assert len(a.history) == 3


# ── AGI Wrapper ────────────────────────────────────────────────────

from empire_os.agi_wrapper import AgiWrapper, wrap_agent


class TestAgiWrapper:
    def test_init(self):
        base = MagicMock()
        base.llm = MagicMock()
        w = AgiWrapper("test-agent", base)
        assert w.name == "test-agent"
        assert w.metrics["cycles"] == 0

    def test_tick_runs_all_three_layers(self):
        base = MagicMock()
        base.llm = MagicMock()
        # Base tick returns a result
        base.tick.return_value = {
            "cycle": 1,
            "decision_preview": "match",
            "result": {"action": "match", "summary": "matched p1"},
        }
        # Base observe returns state
        base.observe.return_value = {"funnel_counts": {"discovered": 5}}
        # Synthetic llm returns examples
        base.llm.structured_chat.return_value = [
            {"input": {}, "expected_output": {}, "rationale": "x"}
        ]
        # ASI observation (no reflection this cycle)
        w = AgiWrapper("test", base)
        result = w.tick()
        assert result["cycle"] == 1
        assert result["synthetic_examples"] >= 0
        # Cycle 1 — not yet ASI reflection (every 5 cycles)
        assert result["asi_strategies"] == []

    def test_tick_asi_reflects_every_5_cycles(self):
        """After 5 wrapper ticks, ASI reflects."""
        base = MagicMock()
        base.llm = MagicMock()
        base.tick.return_value = {
            "cycle": 1, "decision_preview": "x", "result": {"action": "match"},
        }
        base.observe.return_value = {"x": 1}
        base.llm.structured_chat.return_value = {
            "insights": [], "strategies": ["new_strat"]
        }
        w = AgiWrapper("test", base)
        # Tick 5 times — 5th should trigger ASI reflection
        for _ in range(5):
            result = w.tick()
        assert result["asi_strategies"] == ["new_strat"]

    def test_wrap_agent_factory(self):
        base = MagicMock()
        base.llm = MagicMock()
        w = wrap_agent("factory-test", base)
        assert w.name == "factory-test"
        assert isinstance(w, AgiWrapper)

    def test_health_check(self):
        base = MagicMock()
        base.llm = MagicMock()
        base.health_check.return_value = {
            "consecutive_failures": 0, "is_degraded": False,
        }
        w = AgiWrapper("test", base)
        w.metrics["cycles"] = 10
        h = w.health_check()
        assert h["name"] == "test"
        assert h["cycle"] == 10
        assert h["base_health"]["consecutive_failures"] == 0