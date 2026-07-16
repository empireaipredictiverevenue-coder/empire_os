"""Tests for self-heal resilience utilities."""
import time
from unittest.mock import MagicMock

import pytest
from empire_os.self_heal import (
    HealthState,
    with_retry,
    safe_cycle,
    safe_db_op,
    heal_llm_call,
    reset_state_if_stuck,
)


class TestHealthState:
    def test_initial_state(self):
        h = HealthState()
        assert h.consecutive_failures == 0
        assert h.total_failures == 0
        assert h.is_degraded is False
        assert h.last_error is None

    def test_record_success_resets_failures(self):
        h = HealthState()
        h.record_failure("boom")
        h.record_failure("boom")
        assert h.consecutive_failures == 2
        h.record_success()
        assert h.consecutive_failures == 0
        assert h.total_recoveries == 1

    def test_record_failure_increments(self):
        h = HealthState()
        h.record_failure("err1")
        h.record_failure("err2")
        assert h.consecutive_failures == 2
        assert h.total_failures == 2
        assert h.last_error == "err2"

    def test_degraded_after_3_failures(self):
        h = HealthState()
        for i in range(3):
            h.record_failure(f"err{i}")
        assert h.is_degraded is True

    def test_backoff_timing(self):
        h = HealthState()
        h.record_failure("x")
        h.record_failure("x")
        h.enter_backoff(2.0)
        assert h.should_skip_due_to_backoff() is True
        time.sleep(2.1)
        assert h.should_skip_due_to_backoff() is False

    def test_backoff_exponential(self):
        h = HealthState()
        for _ in range(8):  # 2^10 = 1024 > 300 cap
            h.record_failure("x")
        # Should cap at 300s
        assert h.backoff_seconds() == 300


class TestWithRetry:
    def test_success_first_try(self):
        fn = MagicMock(return_value="ok")
        result = with_retry(fn, max_attempts=3, base_delay=0.01)
        assert result == "ok"
        assert fn.call_count == 1

    def test_retries_on_failure(self):
        fn = MagicMock(side_effect=[RuntimeError("1"), RuntimeError("2"), "ok"])
        result = with_retry(fn, max_attempts=3, base_delay=0.01)
        assert result == "ok"
        assert fn.call_count == 3

    def test_raises_after_max_attempts(self):
        fn = MagicMock(side_effect=RuntimeError("always fails"))
        with pytest.raises(RuntimeError):
            with_retry(fn, max_attempts=2, base_delay=0.01)
        assert fn.call_count == 2


class TestSafeCycle:
    def test_returns_result_on_success(self):
        h = HealthState()
        result = safe_cycle(lambda: {"ok": True}, h)
        assert result["ok"] is True
        assert result["value"] == {"ok": True}
        assert h.consecutive_failures == 0

    def test_catches_exception(self):
        h = HealthState()
        result = safe_cycle(lambda: (_ for _ in ()).throw(RuntimeError("boom")), h)
        assert result["ok"] is False
        assert result["status"] == "degraded"
        assert "boom" in result["error"]
        assert h.consecutive_failures == 1


class TestHealLlmCall:
    def test_succeeds_first_try(self):
        llm = MagicMock(return_value={"action": "skip"})
        fallback = MagicMock()
        result = heal_llm_call(llm, fallback, max_attempts=2)
        assert result == {"action": "skip"}
        fallback.assert_not_called()

    def test_uses_fallback_on_failure(self):
        llm = MagicMock(side_effect=RuntimeError("LLM down"))
        fallback = MagicMock(return_value={"action": "skip", "fallback": True})
        result = heal_llm_call(llm, fallback, max_attempts=1)
        assert result["fallback"] is True
        fallback.assert_called_once()

    def test_raises_when_no_fallback(self):
        llm = MagicMock(side_effect=RuntimeError("LLM down"))
        with pytest.raises(RuntimeError):
            heal_llm_call(llm, None, max_attempts=1)


class TestResetStateIfStuck:
    def test_resets_at_threshold(self):
        h = HealthState()
        for _ in range(10):
            h.record_failure("x")
        assert reset_state_if_stuck(h, threshold=10) is True
        assert h.consecutive_failures == 0

    def test_does_not_reset_below_threshold(self):
        h = HealthState()
        for _ in range(5):
            h.record_failure("x")
        assert reset_state_if_stuck(h, threshold=10) is False
        assert h.consecutive_failures == 5