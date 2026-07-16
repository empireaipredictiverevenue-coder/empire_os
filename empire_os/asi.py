"""
ASI — Artificial Superintelligence layer.

Not actual superintelligence — it's a meta-reasoning layer that:

1. Reviews the agent's recent decisions and outcomes
2. Reflects on patterns: where did decisions succeed? where did they fail?
3. Generates improved reasoning strategies for next cycles
4. Adjusts confidence scoring based on historical hit-rate

This is the "self-improvement" loop. Free, runs on existing LLM.
"""
from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("asi")


@dataclass
class DecisionRecord:
    """A historical decision for reflection."""
    cycle: int = 0
    decision: dict = field(default_factory=dict)
    outcome: dict = field(default_factory=dict)
    success: Optional[bool] = None
    observed_at: str = ""


class ASILayer:
    """Meta-reasoning layer that improves the underlying agent over time."""

    def __init__(self, llm, window: int = 20):
        self.llm = llm
        self.history: deque = deque(maxlen=window)
        self.strategies: list = []
        self.metrics = {
            "decisions_tracked": 0,
            "successes": 0,
            "failures": 0,
            "strategies_evolved": 0,
        }

    def record(self, cycle: int, decision: dict, outcome: dict, success: Optional[bool] = None):
        rec = DecisionRecord(
            cycle=cycle, decision=decision, outcome=outcome, success=success,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
        self.history.append(rec)
        self.metrics["decisions_tracked"] += 1
        if success is True:
            self.metrics["successes"] += 1
        elif success is False:
            self.metrics["failures"] += 1

    def reflect(self) -> list:
        """Generate improved strategies based on recent history."""
        if len(self.history) < 3:
            return []  # not enough data

        history_json = [asdict(r) for r in self.history]
        prompt = f"""You are a meta-reasoning layer reviewing recent agent decisions.

Last {len(self.history)} decisions:
{json.dumps(history_json, indent=2)[:3000]}

Analyse:
1. What patterns led to successful decisions?
2. What patterns led to failures?
3. Propose 1-3 refined strategies for next cycles.

Output JSON: {{"insights": [...], "strategies": [...]}}"""

        try:
            result = self.llm.structured_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
        except Exception as e:
            logger.warning("reflection failed: %s", e)
            return []

        strategies = result.get("strategies", []) if isinstance(result, dict) else []
        if strategies:
            self.strategies.extend(strategies)
            self.metrics["strategies_evolved"] += len(strategies)
        return strategies

    def observe(self) -> dict:
        return {
            "agent": "asi-meta-reasoning",
            "decisions_tracked": self.metrics["decisions_tracked"],
            "history_window": len(self.history),
            "strategies_evolved": self.metrics["strategies_evolved"],
            "current_strategies": self.strategies[-3:],
        }

    def reason(self, state: dict) -> str:
        if state.get("history_window", 0) >= 3:
            return json.dumps({"action": "reflect", "reasoning": "enough history to learn from"})
        return json.dumps({"action": "skip", "reasoning": "need more history"})

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip"}
        if d.get("action") == "reflect":
            strategies = self.reflect()
            return {"action": "reflect", "strategies": strategies}
        return {"action": "skip", "summary": "no reflection needed"}