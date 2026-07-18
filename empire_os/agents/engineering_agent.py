"""
Engineering Agent — code/build scout.
Watches for broken services, failed deployments, lint errors, missing
modules, and queues engineering tickets the operator can act on.
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HUB = "http://127.0.0.1:8000"
TICK_INTERVAL = 600  # 10 min


class EngineeringAgent(SyntheticAgent):
    """Engineering layer — finds broken stuff, queues tickets."""

    def observe(self) -> dict:
        state = {"issues": []}

        try:
            r = urllib.request.urlopen(HUB + "/health", timeout=5)
            if "online" not in r.read().decode().lower():
                state["issues"].append("hub not reporting online")
        except Exception as e:
            state["issues"].append("hub unreachable: %s" % e)

        try:
            r = subprocess.run(
                ["incus", "list", "-c", "n,s", "-f", "csv"],
                capture_output=True, text=True, timeout=10
            )
            stopped = []
            for line in r.stdout.strip().split("\n"):
                if "," in line:
                    name, status = line.split(",", 1)
                    if "STOPPED" in status:
                        stopped.append(name.strip())
            state["stopped_containers"] = stopped
            if stopped:
                state["issues"].append("containers stopped: %s" % ", ".join(stopped[:5]))
        except Exception as e:
            state["issues"].append("incus probe failed: %s" % e)

        try:
            r = subprocess.run(
                ["df", "-h", "/root"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.split("\n"):
                if "/dev/" in line:
                    parts = line.split()
                    use_pct = parts[-2] if len(parts) >= 5 else "?"
                    if use_pct.endswith("%") and int(use_pct[:-1]) > 80:
                        state["issues"].append("disk use high: %s" % use_pct)
                    break
        except Exception:
            pass

        try:
            r = subprocess.run(
                ["free", "-m"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.split("\n"):
                if line.startswith("Mem:"):
                    parts = line.split()
                    avail = int(parts[3]) if len(parts) >= 4 else 0
                    if avail < 200:
                        state["issues"].append("low memory: %dMB free" % avail)
                    break
        except Exception:
            pass

        return state

    def reason(self, state: dict) -> str:
        system = (
            "You are the Engineering Agent. Given the current state of "
            "the Empire OS fleet, identify the SINGLE highest-priority "
            "engineering ticket to file. Reply with JSON: "
            '{"ticket": "...", "severity": 1-5, "fix": "..."}'
        )
        prompt = "Issues found: %s" % json.dumps(state.get("issues", []))
        if not state.get("issues"):
            return json.dumps({"ticket": "all-systems-green", "severity": 0, "fix": "none"})
        return self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.2,
            format="json",
        )

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
            ticket_log = Path("/root/engineering/tickets.jsonl")
            ticket_log.parent.mkdir(parents=True, exist_ok=True)
            with ticket_log.open("a") as f:
                f.write(json.dumps({"ts": time.time(), **d}) + "\n")
            return {"summary": "ticket-filed: %s" % d.get("ticket", "")[:60]}
        except Exception as e:
            return {"summary": "ticket-error", "error": str(e)}


if __name__ == "__main__":
    import os
    os.makedirs("/root/engineering", exist_ok=True)
    agent = EngineeringAgent(
        name="engineering-agent",
        role="engineering",
        health_url="http://localhost:9098/health",
    )
    print("Engineering agent starting — tick interval %ds" % TICK_INTERVAL)
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