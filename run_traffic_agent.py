"""Launcher for the Traffic Specialist Agent.

Builds the agent with env-driven LLM backend and runs the observe-reason-act
loop. Separated from the module __main__ so systemd invokes a single,
env-explicit entrypoint (avoids -m path env quirks).
"""
import os
import sys
import time
import json

sys.path.insert(0, "/root/empire_os")

from empire_os.agents.traffic_agent import TrafficSpecialistAgent, TICK_INTERVAL
from empire_os.agent_core import OllamaClient

os.makedirs("/root/traffic", exist_ok=True)

# Explicit env-driven LLM selection. Empty string (not None) bypasses the
# synthetic_agents hardcoded dead remote-Ollama IP and lets OllamaClient fall
# through to OpenRouter via OPENROUTER_API_KEY (or local Ollama).
_llm_url = os.environ.get("LLM_BASE_URL", "") or os.environ.get("OLLAMA_URL", "")
_llm_model = os.environ.get("LLM_MODEL", "") or os.environ.get("OLLAMA_MODEL", "")

agent = TrafficSpecialistAgent(
    name="traffic-agent",
    role="traffic",
    health_url="http://localhost:9105/health",
    llm_url=_llm_url,
    llm_model=_llm_model,
)

print("Traffic specialist agent starting — tick interval %ds (llm=%s)" % (
    TICK_INTERVAL, getattr(agent.llm, "base_url", agent.llm)), flush=True)

# NOTE: we run observe/reason/act directly rather than the framework tick(),
# which hangs in this container (health/syn overhead). The three methods are
# the proven-working path.
consecutive_failures = 0
while True:
    try:
        state = agent.observe()
        decision = agent.reason(state)
        result = agent.act(decision)
        consecutive_failures = 0
        print(json.dumps({
            "cycle": state.get("hub_metrics", {}).get("lanes_total"),
            "summary": result.get("summary", ""),
        }), flush=True)
    except Exception as e:  # noqa: BLE001
        consecutive_failures += 1
        backoff = min(60 * consecutive_failures, 600)
        print(json.dumps({"error": str(e), "backoff": backoff}), flush=True)
        time.sleep(backoff)
        continue
    time.sleep(TICK_INTERVAL)
