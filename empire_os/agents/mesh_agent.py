"""
Mesh Agent — inter-agent coordination layer.
Watches every agent's heartbeat, routes tasks between them, surfaces
cross-agent patterns and bottlenecks to the operator.
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

HUB = "http://127.0.0.1:8000"
REGISTRY = "/root/empire_os/config/agent_registry.json"
TICK_INTERVAL = 60  # seconds


class MeshAgent(SyntheticAgent):
    """Coordination layer — observes all agents, suggests routing."""

    def observe(self) -> dict:
        agents = {}
        if Path(REGISTRY).exists():
            agents = json.loads(Path(REGISTRY).read_text()).get("agents", {})

        health_snapshot = {}
        for name, info in agents.items():
            container = info.get("container", name)
            url = info.get("health_url")
            running = self._is_running(container)
            healthy = False
            if url and running:
                try:
                    r = urllib.request.urlopen(url, timeout=3)
                    healthy = "online" in r.read().decode().lower() or "{" in r.read().decode()
                except Exception:
                    pass
            health_snapshot[name] = {
                "role": info.get("role", "?"),
                "running": running,
                "healthy": healthy,
            }

        try:
            r = urllib.request.urlopen(HUB + "/v1/lanes", timeout=5)
            lanes = json.loads(r.read()).get("total", 0)
        except Exception:
            lanes = 0

        try:
            r = urllib.request.urlopen(HUB + "/v1/leads/counts", timeout=5)
            leads = json.loads(r.read()).get("total", 0)
        except Exception:
            leads = 0

        return {
            "agents_total": len(agents),
            "agents_running": sum(1 for a in health_snapshot.values() if a["running"]),
            "agents_healthy": sum(1 for a in health_snapshot.values() if a["healthy"]),
            "health": health_snapshot,
            "hub_lanes": lanes,
            "hub_leads": leads,
        }

    def reason(self, state: dict) -> str:
        system = (
            "You are the Mesh Agent — the coordinator of an Empire OS v3 "
            "agent fleet. Given the current health snapshot of all agents, "
            "decide ONE concrete action to improve the fleet's coordination. "
            "Reply with JSON: {\"action\": \"...\", \"target\": \"...\", \"why\": \"...\"}"
        )
        prompt = "State: %s\nHealth: %s" % (
            {k: v for k, v in state.items() if k != "health"},
            {k: v for k, v in state["health"].items() if not v["healthy"]},
        )
        raw = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.2,
            format="json",
        )
        try:
            d = json.loads(raw)
            return d.get("action", "no-op") + " | target=" + d.get("target", "n/a")
        except Exception:
            return raw[:200]

    def act(self, decision: str) -> dict:
        return {
            "summary": "mesh-coordination-tick",
            "decision": decision,
            "agents_coordinated": self.context.state.get("agents_total", 0),
        }

    def _is_running(self, container: str) -> bool:
        import subprocess
        try:
            r = subprocess.run(
                ["incus", "list", container, "-c", "s", "-f", "csv"],
                capture_output=True, text=True, timeout=5
            )
            return "RUNNING" in r.stdout
        except Exception:
            return False


if __name__ == "__main__":
    import os
    os.makedirs("/root/mesh", exist_ok=True)
    agent = MeshAgent(
        name="mesh-agent",
        role="mesh",
        health_url="http://localhost:9095/health",
    )
    print("Mesh agent starting — tick interval %ds" % TICK_INTERVAL)
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