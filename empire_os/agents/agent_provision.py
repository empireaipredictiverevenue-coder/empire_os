"""
Empire OS - Agent Provisioning Skill
=====================================
Standardized framework for creating new agents with:
- SKILL.md (capabilities + guardrails)
- SOUL.md (identity + principles) 
- Agent code (extends SyntheticAgent)
- Registration + health endpoint
- Guardrails + observability
"""
from __future__ import annotations

import json
import os
import sys
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict
from jinja2 import Environment

# ─── Paths ─────────────────────────────────────────────────────────────
EMPIRE_ROOT = Path("/root/empire_os")
AGENTS_DIR = EMPIRE_ROOT / "empire_os" / "agents"
SOULS_DIR = AGENTS_DIR / "souls"
SKILLS_DIR = AGENTS_DIR / "skills"
CONFIG_DIR = EMPIRE_ROOT / "config"
LOGS_DIR = EMPIRE_ROOT / "logs"
FEEDBACK_DIR = Path("/root/feedback")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

# ─── Jinja2 Environment ────────────────────────────────────────────────
_jinja_env = Environment()

# ─── Templates ──────────────────────────────────────────────────────────

SKILL_TEMPLATE = """---
name: {{ name }}
description: {{ description }}
category: {{ category }}
version: "1.0"
guardrails:
  - {{ guardrails[0] if guardrails else "Dry-run required before live execution" }}
  - {{ guardrails[1] if guardrails|length > 1 else "No PII in logs" }}
  - {{ guardrails[2] if guardrails|length > 2 else "Rate limit: {{ rate_limit }}" }}
  - Rate limit: {{ rate_limit }}
  - Timeout: {{ timeout }}s
  - No external API calls without key in .env
  - No PII in logs
  - Dry-run mode required before live
triggers:
  - {{ triggers[0] if triggers else "Scheduled tick" }}
  - {{ triggers[1] if triggers|length > 1 else "Hub health degraded" }}
  - {{ triggers[2] if triggers|length > 2 else "Manual dispatch via orchestrator" }}
---

# {{ name }} Skill

## Purpose
{{ purpose }}

## Capabilities
{{ capabilities }}

## Usage
```python
from empire_os.agents.skills.{{ name }} import {{ ClassName }}

agent = {{ ClassName }}()
result = agent.execute({{ example_input }})
```

## Input Schema
{{ input_schema }}

## Output Schema
{{ output_schema }}

## Guardrails
{% for g in guardrails %}
- {{ g }}
{% endfor %}

## Dry-Run
Always test with `--dry-run` before live execution.
"""

SOUL_TEMPLATE = """# {{ name }} — SOUL
*Identity, Principles, Boundaries*

---

## Identity
**Name**: {{ name }}
**Role**: {{ role }}
**Purpose**: {{ purpose }}
**Container**: {{ container }}
**Port**: {{ port }}
**Tick**: {{ tick }}

## Principles
{% for p in principles %}
{{ loop.index }}. **{{ p }}**
{% endfor %}

## Boundaries
- **Scope**: {{ scope }}
- **Cannot**: {{ cannot }}
- **Must**: {{ must }}
- **Escalation**: {{ escalation }}

## Decision Framework
{{ decision_framework }}

## Memory & Learning
- **Log**: `/root/{{ name }}/{{ name }}.log`
- **Feedback**: `/root/feedback/{{ name }}.jsonl`
- **Retention**: {{ retention }}

## Health
- **Endpoint**: `http://localhost:{{ port }}/health`
- **Checks**: {{ health_checks }}
- **Degraded**: {{ degraded_behavior }}

## Soul Signature
> "{{ soul_signature }}"

---

*Written: {{ timestamp }}*
*Version: 1.0*
"""

AGENT_TEMPLATE = '''"""
{{ name }} Agent — {{ description }}
=================================================
{{ purpose }}

Extends SyntheticAgent base. Runs in {{ container }} container on port {{ port }}.
Tick: {{ tick }}.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Load .env
for _ln in (Path("/root/empire_os/.env").read_text(encoding="utf-8").splitlines()
            if Path("/root/empire_os/.env").exists() else ()):
    _ln = _ln.strip()
    if not _ln or _ln.startswith("#") or "=" not in _ln: continue
    _k, _, _v = _ln.partition("=")
    os.environ.setdefault(_k.strip(), _v.strip())

# Import base
sys.path.insert(0, "/root/empire_os")
from empire_os.synthetic_agents import SyntheticAgent


class {{ ClassName }}(SyntheticAgent):
    """{{ name }} agent — {{ role }}."""
    
    NAME = "{{ name }}"
    ROLE = "{{ role }}"
    TICK_SECONDS = {{ tick_seconds }}
    
    def __init__(self, llm_client=None):
        super().__init__(self.NAME, llm_client)
        self.port = {{ port }}
        self.container = "{{ container }}"
        self.soul_path = "/root/empire_os/empire_os/agents/souls/{{ name }}_SOUL.md"
        self._load_soul()
    
    def _load_soul(self):
        """Load soul for identity grounding."""
        try:
            self.soul = Path(self.soul_path).read_text()
        except Exception:
            self.soul = ""
    
    def observe(self) -> dict:
        """Observe environment — return state dict."""
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": self.NAME,
            "role": self.ROLE,
            "port": self.port,
        }
    
    def reason(self, state: dict) -> dict:
        """Reason on observed state — return decision dict."""
        # Override in subclass
        return {"action": "tick", "reason": "base tick"}
    
    def act(self, decision: dict) -> dict:
        """Execute decision — return result dict."""
        # Override in subclass
        return {"status": "ok", "action": decision.get("action", "tick")}
    
    def tick(self):
        """One observe-reason-act cycle."""
        state = self.observe()
        decision = self.reason(state)
        result = self.act(decision)
        self._log_tick(state, decision, result)
        return result
    
    def _log_tick(self, state: dict, decision: dict, result: dict):
        """Log tick to JSONL."""
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": self.NAME,
            "state": state,
            "decision": decision,
            "result": result,
        }
        log_path = Path(f"/root/{{self.NAME}}/{{self.NAME}}.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\\n")
    
    def health(self) -> dict:
        """Health endpoint response."""
        return {
            "status": "ok",
            "agent": self.NAME,
            "role": self.ROLE,
            "port": self.port,
            "container": self.container,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
    
    def run(self):
        """Main loop — runs forever."""
        print(f"[{datetime.now(timezone.utc).isoformat()}] {self.NAME} starting — port {self.port}, tick {self.TICK_SECONDS}s")
        while True:
            try:
                self.tick()
            except Exception as e:
                print(f"[{datetime.now(timezone.utc).isoformat()}] {self.NAME} error: {e}")
            time.sleep(self.TICK_SECONDS)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Run one tick and exit")
    ap.add_argument("--health", action="store_true", help="Print health and exit")
    args = ap.parse_args()
    
    agent = {{ ClassName }}()
    
    if args.health:
        print(json.dumps(agent.health(), indent=2))
    elif args.dry_run:
        result = agent.tick()
        print(json.dumps(result, indent=2))
    else:
        agent.run()
'''

REGISTRY_TEMPLATE = """{
  "{{ name }}": {
    "role": "{{ role }}",
    "container": "{{ container }}",
    "port": {{ port }},
    "tick_seconds": {{ tick_seconds }},
    "health_path": "/health",
    "log_path": "/root/{{ name }}/{{ name }}.log",
    "soul_path": "/root/empire_os/empire_os/agents/souls/{{ name }}_SOUL.md",
    "skill_path": "/root/empire_os/empire_os/agents/skills/{{ name }}.md",
    "code_path": "/root/empire_os/empire_os/agents/{{ name }}_agent.py",
    "enabled": true,
    "created_at": "{{ timestamp }}",
    "guardrails": [
      "dry-run required before live",
      "no PII in logs",
      "rate limit respected",
      "timeout enforced"
    ]
  }
}"""

ORCHESTRATOR_ENTRY = """  "{{ name }}": {
    "role": "{{ role }}",
    "container": "{{ container }}",
    "port": {{ port }},
    "tick_seconds": {{ tick_seconds }},
    "health_path": "/health",
    "log_path": "/root/{{ name }}/{{ name }}.log",
    "soul_path": "/root/empire_os/empire_os/agents/souls/{{ name }}_SOUL.md",
    "skill_path": "/root/empire_os/empire_os/agents/skills/{{ name }}.md",
    "code_path": "/root/empire_os/empire_os/agents/{{ name }}_agent.py",
    "enabled": true,
    "created_at": "{{ timestamp }}"
  },"""


# ─── Provisioning ───────────────────────────────────────────────────────

@dataclass
class AgentSpec:
    name: str                    # snake_case, e.g. "traffic_scout"
    role: str                    # human-readable, e.g. "Traffic Scout"
    purpose: str                 # one sentence
    container: str               # incus container name
    port: int                    # health port
    tick_seconds: int            # tick interval
    category: str = "operations" # operations|growth|engineering|leadership
    principles: list = None
    scope: str = ""
    cannot: str = ""
    must: str = ""
    escalation: str = ""
    decision_framework: str = ""
    retention: str = "90 days"
    health_checks: str = "HTTP 200 on /health"
    degraded_behavior: str = "continue ticking, log degraded"
    soul_signature: str = ""
    guardrails: list = None
    triggers: list = None
    rate_limit: str = "10/min"
    timeout: int = 30
    input_schema: str = "{}"
    output_schema: str = "{}"
    capabilities: str = ""
    
    def __post_init__(self):
        if self.principles is None:
            self.principles = [
                "Observe before acting",
                "Log everything",
                "Dry-run before live",
                "Respect guardrails",
                "Escalate on uncertainty"
            ]
        if self.guardrails is None:
            self.guardrails = [
                "Dry-run required before live execution",
                "No PII in logs",
                f"Rate limit: {self.rate_limit}",
                f"Timeout: {self.timeout}s",
                "No external API calls without .env key",
                "Graceful degradation on dependency failure"
            ]
        if self.triggers is None:
            self.triggers = [
                "Scheduled tick",
                "Hub health degraded",
                "Manual dispatch via orchestrator"
            ]


def provision_agent(spec: AgentSpec) -> dict:
    """Provision a complete agent with all artifacts."""
    timestamp = datetime.now(timezone.utc).isoformat()
    class_name = "".join(word.capitalize() for word in spec.name.split("_"))
    
    # Prepare template context
    ctx = {
        "name": spec.name,
        "role": spec.role,
        "purpose": spec.purpose,
        "container": spec.container,
        "port": spec.port,
        "tick": f"{spec.tick_seconds}s",
        "tick_seconds": spec.tick_seconds,
        "category": spec.category,
        "principles": spec.principles,
        "scope": spec.scope or f"Full {spec.role} operations within Empire OS",
        "cannot": spec.cannot or "Modify other agents' state, access PII, exceed rate limits",
        "must": spec.must or "Log every tick, respect guardrails, escalate on errors",
        "escalation": spec.escalation or "Log to feedback, alert orchestrator, pause on critical",
        "decision_framework": spec.decision_framework or "Observe -> Reason -> Act -> Log -> Learn",
        "retention": spec.retention,
        "health_checks": spec.health_checks,
        "degraded_behavior": spec.degraded_behavior,
        "soul_signature": spec.soul_signature or f"I am {spec.role}. I observe, reason, and act for Empire OS.",
        "guardrails": spec.guardrails,
        "triggers": spec.triggers,
        "rate_limit": spec.rate_limit,
        "timeout": spec.timeout,
        "input_schema": spec.input_schema,
        "output_schema": spec.output_schema,
        "capabilities": spec.capabilities or f"Core {spec.role} operations with full observability",
        "description": f"{spec.role} agent for Empire OS",
        "ClassName": class_name,
        "timestamp": timestamp,
    }
    
    # 1. Create directories
    for d in [SOULS_DIR, SKILLS_DIR, AGENTS_DIR, LOGS_DIR / spec.name]:
        d.mkdir(parents=True, exist_ok=True)
    
    # 2. Write SOUL.md
    soul_path = SOULS_DIR / f"{spec.name}_SOUL.md"
    soul_path.write_text(_jinja_env.from_string(SOUL_TEMPLATE).render(**ctx))
    
    # 3. Write SKILL.md
    skill_path = SKILLS_DIR / f"{spec.name}.md"
    skill_path.write_text(_jinja_env.from_string(SKILL_TEMPLATE).render(**ctx))
    
    # 4. Write agent code
    agent_path = AGENTS_DIR / f"{spec.name}_agent.py"
    agent_path.write_text(_jinja_env.from_string(AGENT_TEMPLATE).render(**ctx))
    
    # 5. Update registry
    registry_path = CONFIG_DIR / "agent_registry.json"
    registry = {}
    if registry_path.exists():
        registry = json.loads(registry_path.read_text())
    registry[spec.name] = json.loads(_jinja_env.from_string(REGISTRY_TEMPLATE).render(**ctx))
    registry_path.write_text(json.dumps(registry, indent=2))
    
    # 6. Generate orchestrator entry
    orchestrator_entry = _jinja_env.from_string(ORCHESTRATOR_ENTRY).render(**ctx)
    
    # 7. Create systemd service file
    service_content = f"""[Unit]
Description=Empire OS {spec.role} Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/empire_os
ExecStart=/root/empire_os/venv/bin/python3 -m empire_os.agents.{spec.name}_agent
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target"""
    service_path = Path(f"/etc/systemd/system/empire-{spec.name}.service")
    try:
        service_path.write_text(service_content)
    except PermissionError:
        pass  # May not have /etc access
    
    return {
        "name": spec.name,
        "role": spec.role,
        "soul_path": str(soul_path),
        "skill_path": str(skill_path),
        "agent_path": str(agent_path),
        "port": spec.port,
        "container": spec.container,
        "orchestrator_entry": orchestrator_entry.strip(),
        "service_path": str(service_path) if service_path.exists() else None,
    }


# ─── CLI ────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Provision new Empire OS agent")
    ap.add_argument("name", help="Agent name (snake_case)")
    ap.add_argument("role", help="Human-readable role")
    ap.add_argument("purpose", help="One-sentence purpose")
    ap.add_argument("--container", default="", help="Incus container name")
    ap.add_argument("--port", type=int, required=True, help="Health port")
    ap.add_argument("--tick", type=int, default=300, help="Tick interval (seconds)")
    ap.add_argument("--category", default="operations", help="Category")
    ap.add_argument("--dry-run", action="store_true", help="Print artifacts without writing")
    args = ap.parse_args()
    
    # Auto-generate container name if not provided
    container = args.container or f"{args.name}-agent"
    
    spec = AgentSpec(
        name=args.name,
        role=args.role,
        purpose=args.purpose,
        container=container,
        port=args.port,
        tick_seconds=args.tick,
        category=args.category,
    )
    
    if args.dry_run:
        class_name = "".join(word.capitalize() for word in args.name.split("_"))
        timestamp = datetime.now(timezone.utc).isoformat()
        ctx = {
            "name": args.name,
            "role": args.role,
            "purpose": args.purpose,
            "container": args.container or f"{args.name}-agent",
            "port": args.port,
            "tick": f"{args.tick}s",
            "tick_seconds": args.tick,
            "category": args.category,
            "principles": [
                "Observe before acting",
                "Log everything",
                "Dry-run before live",
                "Respect guardrails",
                "Escalate on uncertainty"
            ],
            "scope": f"Full {args.role} operations within Empire OS",
            "cannot": "Modify other agents' state, access PII, exceed rate limits",
            "must": "Log every tick, respect guardrails, escalate on errors",
            "escalation": "Log to feedback, alert orchestrator, pause on critical",
            "decision_framework": "Observe -> Reason -> Act -> Log -> Learn",
            "retention": "90 days",
            "health_checks": "HTTP 200 on /health",
            "degraded_behavior": "continue ticking, log degraded",
            "soul_signature": f"I am {args.role}. I observe, reason, and act for Empire OS.",
            "guardrails": [
                "Dry-run required before live execution",
                "No PII in logs",
                "Rate limit: 10/min",
                "Timeout: 30s",
                "No external API calls without .env key",
                "Graceful degradation on dependency failure"
            ],
            "triggers": [
                "Scheduled tick",
                "Hub health degraded",
                "Manual dispatch via orchestrator"
            ],
            "rate_limit": "10/min",
            "timeout": 30,
            "input_schema": "{}",
            "output_schema": "{}",
            "capabilities": f"Core {args.role} operations with full observability",
            "description": f"{args.role} agent for Empire OS",
            "ClassName": "".join(word.capitalize() for word in args.name.split("_")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        service_content = f"""[Unit]
Description=Empire OS {args.role} Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/empire_os
ExecStart=/root/empire_os/venv/bin/python3 -m empire_os.agents.{args.name}_agent
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target"""
        print("=== SOUL.md ===")
        print(_jinja_env.from_string(SOUL_TEMPLATE).render(**ctx))
        print("\n=== SKILL.md ===")
        print(_jinja_env.from_string(SKILL_TEMPLATE).render(**ctx))
        print("\n=== AGENT CODE ===")
        print(_jinja_env.from_string(AGENT_TEMPLATE).render(**ctx)[:1000])
        print("\n=== REGISTRY ENTRY ===")
        print(_jinja_env.from_string(REGISTRY_TEMPLATE).render(**ctx))
        print("\n=== ORCHESTRATOR ENTRY ===")
        print(_jinja_env.from_string(ORCHESTRATOR_ENTRY).render(**ctx))
        print("\n=== SYSTEMD SERVICE ===")
        print(service_content[:500])
        return
    result = provision_agent(spec)
    print(f"Provisioned {result['name']} ({result['role']})")
    print(f"  Soul: {result['soul_path']}")
    print(f"  Skill: {result['skill_path']}")
    print(f"  Code: {result['agent_path']}")
    print(f"  Port: {result['port']}")
    print(f"  Container: {result['container']}")
    if result['orchestrator_entry']:
        print(f"\nAdd to orchestrator registry:")
        print(result['orchestrator_entry'])


if __name__ == "__main__":
    main()