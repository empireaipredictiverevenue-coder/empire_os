"""
AGI Wrapper — combines a base agent with synthetic intelligence and ASI
meta-reasoning. Three layers:

  1. BASE AGENT  — observe/reason/act as usual
  2. SYNTHETIC   — generate synthetic training examples each cycle
  3. ASI         — reflect on recent decisions, evolve strategies

Each layer exposes its own AGI-style observe/reason/act, and the wrapper
threads them together: after the base acts, synthetic augments, ASI
reflects. The next cycle uses ASI's evolved strategies as additional
context for the base agent's reasoning.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_intelligence import SyntheticIntelligence
from empire_os.asi import ASILayer

logger = logging.getLogger("agi_wrapper")


class AgiWrapper:
    """Combines base agent + synthetic intel + ASI meta-reasoning."""

    def __init__(
        self,
        name: str,
        base_agent,
        llm: Optional[OllamaClient] = None,
        synthetic_n: int = 3,
        asi_window: int = 10,
    ):
        self.name = name
        self.base = base_agent
        self.llm = llm or getattr(base_agent, "llm", None) or OllamaClient()
        self.synthetic = SyntheticIntelligence(self.llm, n_synthetic=synthetic_n)
        self.asi = ASILayer(self.llm, window=asi_window)
        self.metrics = {
            "cycles": 0,
            "synthetic_generated": 0,
            "asi_reflections": 0,
        }

    def tick(self) -> dict:
        """Run one full cycle: base → synthetic → ASI reflect."""
        # Layer 1: base agent cycle
        base_result = self.base.tick()
        self.metrics["cycles"] += 1
        cycle = self.metrics["cycles"]
        decision = base_result.get("decision_preview", "")
        result = base_result.get("result", {})

        # Layer 2: synthetic augmentation
        observed = self.base.observe() if hasattr(self.base, "observe") else {}
        synthetic_examples = self.synthetic.augment(observed, result)
        self.metrics["synthetic_generated"] += len(synthetic_examples)

        # Layer 3: ASI reflection (only every 5 cycles to save LLM calls)
        asi_strategies = []
        if cycle % 5 == 0:
            self.asi.record(
                cycle=cycle,
                decision={"preview": decision[:200]},
                outcome=result,
                success=True if result.get("action") != "skip" else None,
            )
            asi_state = self.asi.observe()
            asi_decision = self.asi.reason(asi_state)
            asi_result = self.asi.act(asi_decision)
            asi_strategies = asi_result.get("strategies", [])
            if asi_strategies:
                self.metrics["asi_reflections"] += 1
                logger.info("ASI evolved %d strategies for %s", len(asi_strategies), self.name)
        else:
            # Record history each cycle so reflection has data when triggered
            self.asi.record(
                cycle=cycle,
                decision={"preview": decision[:200]},
                outcome=result,
                success=True if result.get("action") != "skip" else None,
            )

        return {
            "agent": self.name,
            "cycle": cycle,
            "base_result": base_result,
            "synthetic_examples": len(synthetic_examples),
            "asi_strategies": asi_strategies,
            "metrics": dict(self.metrics),
        }

    def health_check(self) -> dict:
        base_health = self.base.health_check() if hasattr(self.base, "health_check") else {}
        return {
            "name": self.name,
            "cycle": self.metrics["cycles"],
            "synthetic_generated": self.metrics["synthetic_generated"],
            "asi_reflections": self.metrics["asi_reflections"],
            "base_health": base_health,
        }


def wrap_agent(
    name: str,
    base_agent,
    llm: Optional[OllamaClient] = None,
    synthetic_n: int = 3,
) -> AgiWrapper:
    """Convenience factory for AgiWrapper."""
    return AgiWrapper(name=name, base_agent=base_agent, llm=llm, synthetic_n=synthetic_n)