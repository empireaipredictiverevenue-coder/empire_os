"""
Self-heal — resilience utilities for AGI agents.

Capabilities:
- LLM call retry with exponential backoff + fallback to heuristic
- DB operation retry on SQLite lock
- Cycle crash isolation (one bad cycle doesn't kill the agent)
- Health tracking per agent (consecutive failures, last success, recovery count)
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("self_heal")


@dataclass
class HealthState:
    """Tracks an agent's health for self-healing decisions."""
    consecutive_failures: int = 0
    total_failures: int = 0
    total_recoveries: int = 0
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_error: Optional[str] = None
    in_backoff_until: float = 0.0
    is_degraded: bool = False

    def record_success(self):
        if self.consecutive_failures > 0:
            self.total_recoveries += 1
            logger.info(
                "self-heal: recovered after %d consecutive failures",
                self.consecutive_failures,
            )
        self.consecutive_failures = 0
        self.last_success_at = _now_iso()
        self.last_error = None
        self.is_degraded = False

    def record_failure(self, error: str):
        self.consecutive_failures += 1
        self.total_failures += 1
        self.last_failure_at = _now_iso()
        self.last_error = error
        if self.consecutive_failures >= 3:
            self.is_degraded = True

    def should_skip_due_to_backoff(self) -> bool:
        return time.time() < self.in_backoff_until

    def enter_backoff(self, seconds: float):
        self.in_backoff_until = time.time() + seconds

    def backoff_seconds(self) -> float:
        """Exponential backoff capped at 300s."""
        return min(2 ** (self.consecutive_failures + 2), 300)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def with_retry(
    fn: Callable,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retry_on: tuple = (Exception,),
    **kwargs,
) -> Any:
    """Retry a function with exponential backoff.

    Returns the result on success. Raises the last exception after
    max_attempts failures.
    """
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except retry_on as e:
            last_error = e
            if attempt == max_attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "retry %d/%d after error: %s (sleeping %.1fs)",
                attempt, max_attempts, e, delay,
            )
            time.sleep(delay)
    raise last_error


def safe_db_op(fn: Callable, *args, **kwargs) -> Any:
    """Run a DB operation with retry on SQLite busy/lock errors."""
    return with_retry(
        fn, *args,
        max_attempts=5,
        base_delay=0.5,
        retry_on=(sqlite3.OperationalError,),
        **kwargs,
    )


def heal_llm_call(
    llm_fn: Callable,
    fallback_fn: Optional[Callable] = None,
    *args,
    max_attempts: int = 2,
    **kwargs,
) -> Any:
    """Call LLM with retry; if all attempts fail, use fallback heuristic."""
    try:
        return with_retry(
            llm_fn, *args,
            max_attempts=max_attempts,
            base_delay=2.0,
            **kwargs,
        )
    except Exception as e:
        logger.warning("LLM call failed after retries: %s", e)
        if fallback_fn:
            logger.info("using heuristic fallback")
            return fallback_fn(*args, **kwargs)
        raise


def safe_cycle(fn: Callable, health: HealthState, *args, **kwargs) -> Optional[dict]:
    """Wrap a full observe-reason-act cycle so crashes don't propagate.

    Returns a dict on both success and failure. The wrapper distinguishes:
      - Success: returns {"ok": True, "value": <fn return>}
      - Failure: returns {"ok": False, "status": "degraded", "error": str(e)}
    """
    try:
        result = fn(*args, **kwargs)
        health.record_success()
        return {"ok": True, "value": result}
    except Exception as e:
        health.record_failure(str(e))
        logger.exception("cycle crashed: %s", e)
        health.enter_backoff(health.backoff_seconds())
        return {
            "ok": False,
            "status": "degraded",
            "error": str(e),
            "recovery_action": f"backoff {health.backoff_seconds():.0f}s",
        }


def reset_state_if_stuck(health: HealthState, threshold: int = 10) -> bool:
    """Reset an agent's state if it's been failing too long.

    Returns True if reset happened.
    """
    if health.consecutive_failures >= threshold:
        logger.error(
            "self-heal: %d consecutive failures, resetting state",
            health.consecutive_failures,
        )
        health.consecutive_failures = 0
        health.is_degraded = False
        health.in_backoff_until = 0.0
        health.total_recoveries += 1
        return True
    return False