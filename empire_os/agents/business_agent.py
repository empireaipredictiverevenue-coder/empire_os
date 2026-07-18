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

HUB = "http://127.0.0.1:8000"
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

        # consume Chief-of-Staff task queue (Growth OS loop closure)
        try:
            cos = "/root/feedback/cos_tasks.jsonl"
            tasks = []
            if os.path.exists(cos):
                with open(cos) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        t = json.loads(line)
                        if not t.get("done"):
                            tasks.append(t)
            state["cos_tasks"] = tasks[:10]
        except Exception:
            state["cos_tasks"] = []

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
        # execute any pending Chief-of-Staff tasks first (loop closure)
        try:
            cos = "/root/feedback/cos_tasks.jsonl"
            if os.path.exists(cos):
                lines = open(cos).read().splitlines()
                out = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    t = json.loads(line)
                    if not t.get("done"):
                        t["done"] = True
                        t["executed_by"] = "business_agent"
                        t["executed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    out.append(json.dumps(t))
                with open(cos, "w") as f:
                    f.write("\n".join(out) + "\n")
        except Exception as e:
            return {"summary": "cos-exec-error", "error": str(e)}
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