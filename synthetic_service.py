"""
SYNTHETIC-INTELLIGENCE-AS-A-SERVICE
====================================
White-label a business's own learning agent. Each tenant gets a lightweight
observe-reason-act learning loop backed by the Empire agent brain (MiniMax M3
via OllamaClient / ApiClient).

Public API:
  - spawn_agent(tenant, domain, goal) -> config dict
  - run_cycle(tenant)                  -> non-empty learning string
  - status(tenant)                     -> agent status dict

Memory persists to /root/feedback/syn_{tenant}.json so the agent learns across
cycles. No DB writes, no daemon changes — pure stdlib + empire_os.agent_core.

Style: terse, stdlib, KISS/DRY. No credentials (agent_core auto-loads .env).
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from empire_os.agent_core import OllamaClient

FEEDBACK_DIR = Path("/root/feedback")
CONFIG_DIR = FEEDBACK_DIR  # config + memory co-located per tenant
LOOP_INTERVAL = 300        # seconds between cycles (default)
LLM_MODEL = "MiniMax-M3"

# In-memory registry of live configs (mirrors persisted config on disk).
_REGISTRY: dict[str, dict] = {}


def _config_path(tenant: str) -> Path:
    return CONFIG_DIR / f"syn_{tenant}.json"


def _load_config(tenant: str) -> dict | None:
    p = _config_path(tenant)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _llm() -> OllamaClient:
    return OllamaClient(model=LLM_MODEL, timeout=180)


def spawn_agent(tenant: str, domain: str, goal: str) -> dict:
    """Create (or refresh) a tenant agent config. Persists to disk."""
    persona = (
        f"You are {tenant}'s autonomous synthetic intelligence agent operating "
        f"in the {domain} vertical. Your standing goal: {goal}. "
        f"You learn every cycle and refine your approach without human input."
    )
    cfg = {
        "tenant": tenant,
        "domain": domain,
        "goal": goal,
        "persona": persona,
        "memory_path": str(_config_path(tenant)),
        "loop_interval": LOOP_INTERVAL,
        "model": LLM_MODEL,
        "spawned_at": datetime.now(timezone.utc).isoformat(),
        "cycles": 0,
        "last_run_at": None,
    }
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    _config_path(tenant).write_text(json.dumps(cfg, indent=2))
    _REGISTRY[tenant] = cfg
    return cfg


def _read_memory(tenant: str) -> list:
    cfg = _load_config(tenant) or _REGISTRY.get(tenant)
    if not cfg:
        return []
    p = Path(cfg["memory_path"])
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        return data.get("learnings", [])
    except Exception:
        return []


def _append_learning(tenant: str, learning: str, meta: dict) -> None:
    cfg = _load_config(tenant) or _REGISTRY.get(tenant)
    if not cfg:
        return
    p = Path(cfg["memory_path"])
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text())
        except Exception:
            data = {}
    data.setdefault("learnings", [])
    data["learnings"].append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "learning": learning,
        **meta,
    })
    data["cycles"] = data.get("cycles", 0) + 1
    data["last_run_at"] = meta.get("ts")
    p.write_text(json.dumps(data, indent=2))


def run_cycle(tenant: str) -> str:
    """Run one learning cycle: read memory, ask the brain, append learning.

    Returns a non-empty learning string (the newest insight). On any failure
    returns a short fallback learning string rather than raising.
    """
    cfg = _load_config(tenant) or _REGISTRY.get(tenant)
    if not cfg:
        return f"no agent spawned for '{tenant}' — call spawn_agent first"

    memory = _read_memory(tenant)
    mem_block = ""
    if memory:
        recent = "\n".join(f"- {m['learning']}" for m in memory[-5:])
        mem_block = f"\n\nWhat you already learned (do not repeat):\n{recent}"

    sys_prompt = cfg["persona"]
    user_prompt = (
        f"GOAL: {cfg['goal']}\n"
        f"DOMAIN: {cfg['domain']}\n"
        f"Cycle #{len(memory) + 1}. Produce ONE concrete, actionable learning "
        f"that moves you toward the goal. Be specific and terse (<= 2 sentences)."
        f"{mem_block}"
    )

    try:
        llm = _llm()
        raw = llm.chat(
            messages=[{"role": "user", "content": user_prompt}],
            system=sys_prompt,
            temperature=0.4,
        )
        # Strip <think>...</think> blocks some models emit, then trim.
        import re as _re
        cleaned = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.DOTALL).strip()
        learning = cleaned or raw.strip()
        if not learning:
            learning = f"cycle {len(memory)+1}: no signal — refine observation"
    except Exception as e:
        learning = f"cycle {len(memory)+1}: brain error ({str(e)[:80]})"

    meta = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tenant": tenant,
        "domain": cfg["domain"],
        "cycle": len(memory) + 1,
    }
    _append_learning(tenant, learning, meta)
    # keep registry/disk config cycle count in sync
    cfg["cycles"] = len(memory) + 1
    cfg["last_run_at"] = meta["ts"]
    try:
        c = _load_config(tenant) or {}
        c.update({k: cfg[k] for k in ("cycles", "last_run_at")})
        _config_path(tenant).write_text(json.dumps(c, indent=2))
    except Exception:
        pass
    return learning


def status(tenant: str) -> dict:
    """Return agent status: config, cycle count, last learning, health."""
    cfg = _load_config(tenant) or _REGISTRY.get(tenant)
    if not cfg:
        return {"tenant": tenant, "alive": False, "reason": "not spawned"}
    memory = _read_memory(tenant)
    return {
        "tenant": tenant,
        "alive": True,
        "domain": cfg.get("domain"),
        "goal": cfg.get("goal"),
        "cycles": len(memory),
        "loop_interval": cfg.get("loop_interval"),
        "model": cfg.get("model"),
        "last_run_at": cfg.get("last_run_at"),
        "last_learning": memory[-1]["learning"] if memory else None,
        "memory_path": cfg.get("memory_path"),
    }


# Re-export so callers can drive a quick local loop if desired.
def run_until(tenant: str, max_cycles: int = 1):
    out = []
    for _ in range(max_cycles):
        out.append(run_cycle(tenant))
        time.sleep(0.1)
    return out


if __name__ == "__main__":
    # smoke test
    c = spawn_agent("testco", "logistics", "find buyers")
    print("spawned:", c["tenant"], c["domain"])
    print("learning:", run_cycle("testco"))
    print("status:", status("testco"))
