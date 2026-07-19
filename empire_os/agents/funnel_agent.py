"""
Funnel Agent — funnel operations + state management.
Watches every prospect's journey through the funnel:
  discovered → matched → outreach_drafted → outreach_sent
              → replied → claimed → settled

Surfaces:
  - Stuck prospects (in same state too long)
  - Drop-off rates between states
  - Bottleneck stages (where leads queue)
  - Auto-transition candidates (leads ready for next step)
  - Funnel velocity (avg time between transitions)

All transitions require operator approval. The agent drafts; the
operator approves.
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HUB = "http://127.0.0.1:8081"
TICK_INTERVAL = 300  # 5 min — funnel ops need to be fast


class FunnelAgent(SyntheticAgent):
    """Funnel operations layer — surfaces stuck prospects + transitions."""

    def observe(self) -> dict:
        state = {"states": {}, "prospects": [], "stuck": []}

        try:
            r = urllib.request.urlopen(HUB + "/v1/funnel/counts", timeout=5)
            state["states"] = json.loads(r.read())
        except Exception as e:
            state["error"] = str(e)

        for s in ("discovered", "matched", "outreach_drafted",
                  "outreach_sent", "replied", "claimed"):
            try:
                r = urllib.request.urlopen(
                    HUB + "/v1/funnel/states?state=%s&limit=20" % s, timeout=5)
                state["prospects"].extend(json.loads(r.read()).get("prospects", []))
            except Exception:
                pass

        stuck_log = Path("/root/funnel/stuck.jsonl")
        if stuck_log.exists():
            with stuck_log.open() as f:
                state["stuck"] = [json.loads(line) for line in f if line.strip()][-10:]

        return state

    def reason(self, state: dict) -> str:
        system = (
            "You are the Funnel Agent for Empire OS v3. Given the current "
            "funnel state, identify the SINGLE most important funnel "
            "intervention. Reply with JSON: "
            '{"intervention": "...", "target_state": "...", "expected_lift": "..."}'
        )
        prompt = "Funnel state: %s" % json.dumps(state, default=str)[:2000]
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.3,
            format="json",
        )

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
            out = Path("/root/funnel/interventions.jsonl")
            out.parent.mkdir(parents=True, exist_ok=True)
            d["ts"] = time.time()
            d["status"] = "pending-operator-review"
            with out.open("a") as f:
                f.write(json.dumps(d) + "\n")
            return {"summary": "funnel-intervention: %s" % d.get("intervention", "")[:60]}
        except Exception as e:
            return {"summary": "funnel-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/funnel", exist_ok=True)
    agent = FunnelAgent(
        name="funnel-agent",
        role="funnel",
        health_url="http://localhost:9104/health",
    )
    print("Funnel agent starting — tick interval %ds" % TICK_INTERVAL)
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