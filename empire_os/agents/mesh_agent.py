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

HUB = "http://127.0.0.1:8081"
REGISTRY = "/root/empire_os/config/agent_registry.json"
HEARTBEATS = "/root/empire_os/config/agent_heartbeats.json"
MESH_REPORT = "/root/empire_os/config/mesh_report.json"
TICK_INTERVAL = 60  # seconds


class MeshAgent(SyntheticAgent):
    """Coordination layer — observes all agents, suggests routing.

    Rule-based mode (--no-llm) runs WITHOUT Ollama: reads agent_heartbeats.json
    + agent_registry.json, names the bottleneck, writes mesh_report.json.
    LLM mode (default) uses Ollama for natural-language routing when reachable.
    """

    def __init__(self, *a, rule_mode=False, **k):
        super().__init__(*a, **k, disable_llm=rule_mode)
        self.rule_mode = rule_mode
        if rule_mode:
            self.llm = None  # no Ollama needed

    def observe(self) -> dict:
        agents = {}
        if Path(REGISTRY).exists():
            agents = json.loads(Path(REGISTRY).read_text()).get("agents", {})

        health_snapshot = {}
        for name, info in agents.items():
            container = info.get("container", name)
            url = info.get("health_url")
            running = self._is_running(container)
            if not running:
                # Blueprint agent whose container was never provisioned/started.
                # Not "unhealthy" — just not deployed yet. Don't try to restart it.
                health_snapshot[name] = {
                    "role": info.get("role", "?"),
                    "running": False,
                    "healthy": False,
                    "not_provisioned": True,
                }
                continue
            healthy = False
            if url:
                try:
                    r = urllib.request.urlopen(url, timeout=3)
                    body = r.read().decode().lower()
                    healthy = "online" in body or "{" in body
                except Exception:
                    pass
            health_snapshot[name] = {
                "role": info.get("role", "?"),
                "running": running,
                "healthy": healthy,
            }

        # also fold in harness heartbeats (standalone agents)
        hb = {}
        if Path(HEARTBEATS).exists():
            try:
                hb = json.loads(Path(HEARTBEATS).read_text())
            except Exception:
                hb = {}
        for name, st in hb.items():
            if name not in health_snapshot:
                health_snapshot[name] = {
                    "role": "standalone",
                    "running": st.get("status") in ("OK",),
                    "healthy": st.get("status") in ("OK",),
                    "harness_status": st.get("status"),
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
            "agents_total": len(health_snapshot),
            "agents_running": sum(1 for a in health_snapshot.values() if a.get("running")),
            "agents_healthy": sum(1 for a in health_snapshot.values() if a.get("healthy")),
            "health": health_snapshot,
            "hub_lanes": lanes,
            "hub_leads": leads,
        }

    def rule_reason(self, state: dict) -> str:
        """Rule-based: name the bottleneck agent (per SOUL principle 3)."""
        unhealthy = {k: v for k, v in state["health"].items()
                     if v.get("running") and not v.get("healthy")}
        blocked = {k: v for k, v in state["health"].items()
                   if v.get("harness_status") == "BLOCKED"}
        not_provisioned = [k for k, v in state["health"].items()
                           if v.get("not_provisioned")]
        if unhealthy:
            name = next(iter(unhealthy))
            return f"restart|target={name}|why={name} running but not healthy"
        if blocked:
            name = next(iter(blocked))
            return f"warn|target={name}|why={name} BLOCKED (needs Ollama for LLM mode)"
        if state["hub_leads"] == 0:
            return "warn|target=hub|why=hub reports 0 leads — sweep/pipeline stalled"
        np = len(not_provisioned)
        return (f"noop|target=none|why=fleet healthy; "
                f"{np} blueprint agents not yet provisioned (expected)")

    def reason(self, state: dict) -> str:
        if self.rule_mode or self.llm is None:
            return self.rule_reason(state)
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
        # write mesh coordination report (rule-based, auditable)
        Path(MESH_REPORT).parent.mkdir(parents=True, exist_ok=True)
        Path(MESH_REPORT).write_text(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "mode": "rule" if (self.rule_mode or self.llm is None) else "llm",
        }, indent=2))
        return {
            "summary": "mesh-coordination-tick",
            "decision": decision,
            "agents_coordinated": self.context.state.get("agents_total", 0)
            if hasattr(self, "context") else 0,
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
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true",
                    help="rule-based mode (no Ollama needed)")
    a = ap.parse_args()
    os.makedirs("/root/mesh", exist_ok=True)
    agent = MeshAgent(
        name="mesh-agent",
        role="mesh",
        health_url="http://localhost:9095/health",
        rule_mode=a.no_llm,
    )
    mode = "RULE-BASED (no Ollama)" if a.no_llm else "LLM"
    print("Mesh agent starting — %s — tick interval %ds" % (mode, TICK_INTERVAL))
    consecutive_failures = 0
    while True:
        try:
            result = agent.tick()
            consecutive_failures = 0
            print(json.dumps({"cycle": result.get("cycle"), "summary": result.get("result", {}).get("summary", ""), "decision": result.get("result", {}).get("decision", "")}))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            print(json.dumps({"error": str(e), "backoff": backoff, "failures": consecutive_failures}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)