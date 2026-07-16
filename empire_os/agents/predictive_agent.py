"""
Predictive Agent — runs the revenue/gap/leak/waste formulas and
writes a daily report that the operator can review.

Runs as part of the agentic loop on its own natural cadence (daily).
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

TICK_INTERVAL = 86400  # 24 hours


class PredictiveAgent(SyntheticAgent):
    """Daily predictive analysis — runs revenue + gap + leak formulas."""

    def observe(self) -> dict:
        try:
            from empire_os.predictive import generate_daily_report
            from empire_os.revenue_goals import fleet_summary
            report = generate_daily_report()
            goals = fleet_summary()
            return {"revenue_report": report, "fleet_goals": goals}
        except Exception as e:
            return {"error": str(e)}

    def reason(self, state: dict) -> str:
        if state.get("error"):
            return json.dumps({"action": "no-report", "error": state["error"]})

        rev = state.get("revenue_report", {}).get("revenue", {})
        goals = state.get("fleet_goals", {})
        fleet = goals.get("fleet", {})
        agents = goals.get("agents", {})

        stalled = [a for a, p in agents.items() if p.get("status") == "stalled"]
        behind = [a for a, p in agents.items() if p.get("status") == "behind"]

        system = (
            "You are the Predictive Agent for Empire OS v3. Given today's "
            "revenue projection AND the fleet's per-agent revenue goals, "
            "pick the SINGLE most important finding the operator should act "
            "on. Reply with JSON: "
            '{"finding": "...", "category": "revenue|gap|leak|goal|agent", '
            '"severity": 1-5, "action": "..."}'
        )
        prompt = (
            "Revenue projection:\n%s\n\n"
            "Fleet goals:\n  weekly target: $%s\n  actual: $%s (%s%%)\n"
            "  stalled agents: %s\n  behind agents: %s"
        ) % (
            json.dumps({
                "active_mrr": rev.get("active_seats_mrr"),
                "unrealized_mrr": rev.get("unrealized_mrr"),
                "confidence": rev.get("confidence"),
            }, default=str),
            fleet.get("weekly_target_mrr", 0),
            fleet.get("actual_mrr", 0),
            fleet.get("progress_pct", 0),
            stalled,
            behind,
        )
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.3,
            format="json",
        )

    def act(self, decision: str) -> dict:
        out = Path("/root/predictive/findings.jsonl")
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            d = json.loads(decision)
            d["ts"] = time.time()
            with out.open("a") as f:
                f.write(json.dumps(d) + "\n")
            return {"summary": "predictive-finding: %s" % d.get("finding", "")[:60]}
        except Exception as e:
            return {"summary": "predictive-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/predictive", exist_ok=True)
    agent = PredictiveAgent(
        name="predictive-agent",
        role="predictive",
    )
    print("Predictive agent starting — tick interval %ds" % TICK_INTERVAL)
    consecutive_failures = 0
    while True:
        try:
            result = agent.tick()
            consecutive_failures = 0
            print(json.dumps({"cycle": result.get("cycle"), "summary": result.get("result", {}).get("summary", "")}))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            print(json.dumps({"error": str(e), "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)