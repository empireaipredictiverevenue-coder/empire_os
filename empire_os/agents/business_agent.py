"""
Business Agent — operator-facing strategy layer.
Daily brief builder, decision surfacer, KPI tracker.
Reads funnel + revenue + lead metrics and recommends business moves.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HUB = "http://10.118.155.218:8081"
TICK_INTERVAL = 3600  # 1 hour


class BusinessAgent(SyntheticAgent):
    """Strategy layer — reads business metrics, surfaces decisions."""

    def observe(self) -> dict:
        state = {}
        try:
            r = urllib.request.urlopen(HUB + "/v1/leads/counts", timeout=5)
            state["leads"] = json.loads(r.read())
        except Exception as e:
            state["leads_error"] = str(e)

        try:
            r = urllib.request.urlopen(HUB + "/v1/lanes", timeout=10)
            state["lanes"] = json.loads(r.read())
        except Exception as e:
            state["lanes_error"] = str(e)

        try:
            r = urllib.request.urlopen(HUB + "/v1/funnel/counts", timeout=5)
            state["funnel"] = json.loads(r.read())
        except Exception as e:
            state["funnel_error"] = str(e)

        return state

    def reason(self, state: dict) -> str:
        system = (
            "You are the Business Agent for Empire OS v3. You read "
            "funnel + lead + lane metrics and surface the TOP business "
            "decision the operator should make today. Reply with JSON: "
            '{"decision": "...", "priority": 1-5, "rationale": "..."}'
        )
        prompt = "Business state: %s" % json.dumps(state, default=str)[:2000]
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.3,
            format="json",
        )

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
            decisions_log = Path("/root/business/decisions.jsonl")
            decisions_log.parent.mkdir(parents=True, exist_ok=True)
            with decisions_log.open("a") as f:
                f.write(json.dumps({"ts": time.time(), **d}) + "\n")
            return {"summary": "decision-logged: %s" % d.get("decision", "")[:60]}
        except Exception as e:
            return {"summary": "decision-parse-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/business", exist_ok=True)
    agent = BusinessAgent(
        name="business-agent",
        role="business",
        health_url="http://localhost:9096/health",
    )
    print("Business agent starting — tick interval %ds" % TICK_INTERVAL)
    consecutive_failures = 0
    while True:
        try:
            result = agent.tick()
            consecutive_failures = 0
            print(json.dumps({"cycle": result.get("cycle"), "summary": result.get("result", {}).get("summary", "")}))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            print(json.dumps({"error": str(e), "backoff": backoff, "failures": consecutive_failures}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)