"""
Growth Agent — market opportunity + ad-gen + AEO gap hunter.
Scans the lead funnel for underserved niches, suggests new AEO pages,
monitors ad-gen pipeline output, surfaces growth levers.
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
TICK_INTERVAL = 1800  # 30 min


class GrowthAgent(SyntheticAgent):
    """Growth layer — finds gaps and surfaces opportunities."""

    def observe(self) -> dict:
        state = {}
        try:
            r = urllib.request.urlopen(HUB + "/v1/lanes", timeout=10)
            lanes = json.loads(r.read())
            occupied = [l for l in lanes.get("lanes", []) if l.get("occupied_by")]
            state["lanes_total"] = lanes.get("total", 0)
            state["lanes_occupied"] = len(occupied)
            state["lanes_empty"] = state["lanes_total"] - state["lanes_occupied"]
        except Exception as e:
            state["error"] = str(e)

        try:
            r = urllib.request.urlopen(HUB + "/v1/aeo/pages", timeout=10)
            state["aeo_pages"] = len(json.loads(r.read()).get("pages", []))
        except Exception:
            state["aeo_pages"] = 0

        try:
            r = urllib.request.urlopen(HUB + "/v1/leads?limit=100", timeout=10)
            leads = json.loads(r.read()).get("leads", [])
            niches = {}
            for lead in leads:
                n = lead.get("niche", "?")
                niches[n] = niches.get(n, 0) + 1
            state["lead_niches"] = sorted(niches.items(), key=lambda x: -x[1])[:10]
        except Exception:
            state["lead_niches"] = []

        return state

    def reason(self, state: dict) -> str:
        system = (
            "You are the Growth Agent. Find the SINGLE biggest growth "
            "opportunity from this snapshot. Reply with JSON: "
            '{"opportunity": "...", "expected_lift": "high|medium|low", "action": "..."}'
        )
        prompt = "Growth state: %s" % json.dumps(state, default=str)[:2000]
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.3,
            format="json",
        )

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
            opp_log = Path("/root/growth/opportunities.jsonl")
            opp_log.parent.mkdir(parents=True, exist_ok=True)
            with opp_log.open("a") as f:
                f.write(json.dumps({"ts": time.time(), **d}) + "\n")
            return {"summary": "growth-opportunity: %s" % d.get("opportunity", "")[:60]}
        except Exception as e:
            return {"summary": "growth-parse-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/growth", exist_ok=True)
    agent = GrowthAgent(
        name="growth-agent",
        role="growth",
        health_url="http://localhost:9097/health",
    )
    print("Growth agent starting — tick interval %ds" % TICK_INTERVAL)
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