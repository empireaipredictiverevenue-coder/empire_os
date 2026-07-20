#!/usr/bin/env python3
"""Empire OS — Agent Harness (fleet launch + heartbeat verification).

Minimal harness: proves every agent RUNS (imports + executes one tick)
before we wire networking (mesh) between them. Targets standalone,
no-LLM agents (behavior_engine, leadership_council, predictive_revenue,
eval_connect_sweeps) — the ones that work without Ollama.

LLM-dependent agents (mesh, SyntheticAgent subclasses) need Ollama
reachable first; the harness reports them as BLOCKED, not failed.

Registry: /root/empire_os/config/agent_heartbeats.json
Run: /root/venv/bin/python3 empire_os/agent_harness.py
"""
import json, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
REGISTRY = "/root/empire_os/config/agent_heartbeats.json"

# standalone agents we can run NOW (no LLM)
STANDALONE = {
    "behavior_engine": ("empire_os.behavior_engine", "main"),
    "leadership_council": ("empire_os.leadership_council", "run"),
    "predictive_revenue": ("empire_os.predictive_revenue", "forecast"),
    "eval_connect_sweeps": ("empire_os.eval_connect_sweeps", "main"),
}

# LLM-dependent (blocked until Ollama reachable)
LLM_AGENTS = ["mesh_agent", "ceo", "cto", "chief_of_staff"]


def _beat(name: str, status: str, detail: str):
    reg = {}
    if Path(REGISTRY).exists():
        try:
            reg = json.loads(Path(REGISTRY).read_text())
        except Exception:
            reg = {}
    reg[name] = {
        "status": status, "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    Path(REGISTRY).parent.mkdir(parents=True, exist_ok=True)
    Path(REGISTRY).write_text(json.dumps(reg, indent=2))
    return reg


def run_standalone(name: str, mod: str, fn: str) -> dict:
    try:
        t = time.time()
        m = __import__(mod, fromlist=[fn])
        func = getattr(m, fn)
        res = func()
        dt = time.time() - t
        _beat(name, "OK", f"ran {fn} in {dt:.2f}s")
        return {"name": name, "status": "OK", "ms": round(dt * 1000)}
    except Exception as e:
        _beat(name, "FAIL", f"{type(e).__name__}: {e}")
        return {"name": name, "status": "FAIL", "error": str(e)}


def main() -> dict:
    results = []
    for name, (mod, fn) in STANDALONE.items():
        results.append(run_standalone(name, mod, fn))
    for name in LLM_AGENTS:
        _beat(name, "BLOCKED", "needs Ollama reachable (networking phase)")
        results.append({"name": name, "status": "BLOCKED",
                        "reason": "Ollama unreachable"})
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": sum(1 for r in results if r["status"] == "OK"),
        "fail": sum(1 for r in results if r["status"] == "FAIL"),
        "blocked": sum(1 for r in results if r["status"] == "BLOCKED"),
        "agents": results,
    }
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
