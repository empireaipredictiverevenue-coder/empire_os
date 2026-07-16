"""
Traffic Specialist Agent — acquisition + paid/organic traffic ops.
Watches lead sources (organic search, paid ads, social, referral),
monitors cost-per-lead, channel ROI, and proposes traffic allocation
moves for the operator to approve.

The agent is read-only against any traffic platform — it surfaces
recommendations, the operator pulls levers in Google Ads / Meta / etc.
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


class TrafficSpecialistAgent(SyntheticAgent):
    """Acquisition layer — channel ROI + allocation recommendations."""

    def observe(self) -> dict:
        state = {"leads": [], "by_niche": {}, "hub_metrics": {}}

        try:
            r = urllib.request.urlopen(HUB + "/v1/lanes", timeout=10)
            lanes = json.loads(r.read())
            state["hub_metrics"]["lanes_total"] = lanes.get("total", 0)
            state["hub_metrics"]["lanes_occupied"] = sum(
                1 for l in lanes.get("lanes", []) if l.get("occupied_by")
            )
        except Exception as e:
            state["error"] = str(e)

        try:
            r = urllib.request.urlopen(HUB + "/v1/leads?limit=100", timeout=10)
            leads = json.loads(r.read()).get("leads", [])
            state["leads"] = leads
            for lead in leads:
                niche = lead.get("niche", "?")
                metro = lead.get("metro", "?")
                key = "%s:%s" % (niche, metro)
                state["by_niche"][key] = state["by_niche"].get(key, 0) + 1
        except Exception:
            pass

        return state

    def reason(self, state: dict) -> str:
        if not state.get("by_niche"):
            return json.dumps({"action": "no-traffic-yet"})

        system = (
            "You are the Traffic Specialist for Empire OS v3. Given the "
            "current lead distribution, recommend where to allocate traffic "
            "spend for maximum ROI. Reply with JSON: "
            '{"channel": "organic|paid_search|paid_social|referral", '
            '"allocation_pct": 0-100, "rationale": "..."}'
        )
        top_niches = sorted(state["by_niche"].items(), key=lambda x: -x[1])[:10]
        prompt = "Top performing niche+metros: %s" % json.dumps(top_niches)
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.4,
            format="json",
        )

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
            out = Path("/root/traffic/recommendations.jsonl")
            out.parent.mkdir(parents=True, exist_ok=True)
            d["ts"] = time.time()
            d["status"] = "pending-operator-review"
            with out.open("a") as f:
                f.write(json.dumps(d) + "\n")
            return {"summary": "traffic-rec: %s" % d.get("channel", "")[:50]}
        except Exception as e:
            return {"summary": "traffic-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/traffic", exist_ok=True)
    agent = TrafficSpecialistAgent(
        name="traffic-agent",
        role="traffic",
        health_url="http://localhost:9105/health",
    )
    print("Traffic specialist agent starting — tick interval %ds" % TICK_INTERVAL)
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