"""
Scheduling Agent — bookings + appointments for leads.
When a lead reaches 'claimed' state, the scheduling agent proposes
appointment slots and writes them to the hub. Operator approves,
system sends confirmation to the lead.
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HUB = "http://127.0.0.1:8081"
TICK_INTERVAL = 300  # 5 min


class SchedulingAgent(SyntheticAgent):
    """Scheduling layer — proposes slots for claimed leads."""

    def observe(self) -> dict:
        state = {"claimed_leads": [], "scheduled": 0}

        try:
            r = urllib.request.urlopen(HUB + "/v1/funnel/states?state=claimed&limit=50", timeout=10)
            claimed = json.loads(r.read())
            for p in claimed.get("prospects", []):
                state["claimed_leads"].append({
                    "id": p.get("prospect_id"),
                    "niche": p.get("notes", "").split("=")[-1] if "=" in p.get("notes", "") else "?",
                    "state": p.get("current_state"),
                })
        except Exception as e:
            state["error"] = str(e)

        sched_log = Path("/root/scheduling/appointments.jsonl")
        if sched_log.exists():
            with sched_log.open() as f:
                state["scheduled"] = sum(1 for _ in f)

        return state

    def reason(self, state: dict) -> str:
        claimed = state.get("claimed_leads", [])
        if not claimed:
            return json.dumps({"action": "no-leads-to-schedule"})

        system = (
            "You are the Scheduling Agent. For claimed leads, propose "
            "appointment slots. Reply with JSON: "
            '{"slots": [{"lead_id": "...", "datetime": "ISO", "channel": "phone|video|in-person"}]}'
        )
        prompt = "Claimed leads needing scheduling: %s" % json.dumps(claimed[:10])
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.2,
            format="json",
        )

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
            slots = d.get("slots", [])
            if not slots:
                return {"summary": "no-slots-proposed"}

            sched_log = Path("/root/scheduling/appointments.jsonl")
            sched_log.parent.mkdir(parents=True, exist_ok=True)

            for slot in slots:
                slot["proposed_at"] = datetime.now(timezone.utc).isoformat()
                slot["status"] = "pending-operator-approval"
                with sched_log.open("a") as f:
                    f.write(json.dumps(slot) + "\n")

            return {"summary": "scheduled-%d-leads" % len(slots), "count": len(slots)}
        except Exception as e:
            return {"summary": "scheduling-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/scheduling", exist_ok=True)
    agent = SchedulingAgent(
        name="scheduling-agent",
        role="scheduling",
        health_url="http://localhost:9099/health",
    )
    print("Scheduling agent starting — tick interval %ds" % TICK_INTERVAL)
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