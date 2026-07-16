"""
Agent Core — base class for AGI-driven observe-reason-act loops.

Every agent in Empire OS v3 follows this pattern:
1. **observe()** — gather state from funnel DB, AEO surface, market
2. **reason()** — LLM call to decide what action to take
3. **act()** — execute the decision, write results back

Agents run autonomously via the Orchestrator, replacing cron scripts.
"""
from __future__ import annotations

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("agent_core")


# ── Auto-load .env so MINIMAX_API_KEY is available ─────────────────────
_ENV_PATH = Path("/root/empire_os/.env")
if _ENV_PATH.exists():
    try:
        for _ln in _ENV_PATH.read_text().splitlines():
            _ln = _ln.strip()
            if not _ln or _ln.startswith("#") or "=" not in _ln:
                continue
            _k, _v = _ln.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass


# ── Ollama LLM Client ────────────────────────────────────────────────

class OllamaClient:
    """Lightweight client for Ollama on ornith-agent:11434."""

    def __init__(
        self,
        base_url: str = "http://10.218.156.211:11434",
        model: str = "qwen2.5:7b",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._session = None

    def _post(self, payload: dict) -> dict:
        """HTTP POST to Ollama API."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/api/chat"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            logger.warning("Ollama call failed: %s", e)
            return {"error": str(e)}

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.3,
        format: Optional[str] = None,  # "json" for structured output
    ) -> str:
        """Send a chat request and return the response text."""
        if system:
            messages = [{"role": "system", "content": system}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format:
            payload["format"] = format

        result = self._post(payload)
        if "error" in result:
            return json.dumps({"error": result["error"], "fallback": True})

        msg = result.get("message", {})
        return msg.get("content", "")

    def structured_chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> dict:
        """Chat with JSON-structured output guaranteed."""
        raw = self.chat(
            messages=messages,
            system=system,
            temperature=temperature,
            format="json",
        )
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"error": "Failed to parse structured output", "raw": raw}


# ── OpenAI-compatible API Client (MiniMax, OpenAI, etc.) ──────────────

class ApiClient:
    """OpenAI-compatible LLM client (MiniMax M3, OpenAI, etc.).

    Activated automatically when MINIMAX_API_KEY is set in the environment.
    Falls back to OllamaClient otherwise.
    """

    def __init__(
        self,
        base_url: str = "",
        model: str = "",
        timeout: int = 30,
        api_key: str = "",
    ):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        # When MINIMAX is configured, any passed Ollama URL is ignored
        if self.api_key and base_url and ("localhost" in base_url or "11434" in base_url or "ollama" in base_url.lower()):
            base_url = ""
        self.base_url = (
            base_url or os.environ.get("LLM_BASE_URL", "https://api.minimax.io/v1")
        ).rstrip("/")
        self.model = (
            model or os.environ.get("LLM_MODEL", "MiniMax-M2.7-highspeed")
        )
        self.timeout = timeout

    def _post(self, payload: dict) -> dict:
        """HTTP POST to an OpenAI-compatible /chat/completions endpoint."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/chat/completions"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            logger.warning("API call failed: %s", e)
            return {"error": str(e)}

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.3,
        format: Optional[str] = None,
    ) -> str:
        """Send a chat request and return the response text."""
        if system:
            messages = [{"role": "system", "content": system}] + messages

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if format == "json":
            payload["response_format"] = {"type": "json_object"}

        result = self._post(payload)
        if "error" in result:
            return json.dumps({"error": result["error"], "fallback": True})

        choice = result.get("choices", [{}])[0]
        msg = choice.get("message", {})
        return msg.get("content", "")

    def structured_chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> dict:
        """Chat with JSON-structured output guaranteed."""
        raw = self.chat(
            messages=messages,
            system=system,
            temperature=temperature,
            format="json",
        )
        # Strip <think>...</think> blocks that some models emit
        import re as _re
        stripped = _re.sub(r'<think>.*?</think>', '', raw, flags=_re.DOTALL).strip()
        stripped = _re.sub(r'<.*?thinking.*?>.*?</.*?>', '', stripped, flags=_re.DOTALL).strip()
        # Strip Markdown code fences (```json ... ```, ``` ... ```)
        stripped = _re.sub(r'^```\w*\s*', '', stripped).strip()
        stripped = _re.sub(r'\s*```$', '', stripped).strip()
        # If all that's left isn't JSON, try to find a JSON object in it
        stripped = _re.sub(r'^[^{]*', '', stripped).strip()  # drop leading non-JSON
        stripped = _re.sub(r'[^}]*$', '', stripped).strip()  # drop trailing non-JSON
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            return {"error": "Failed to parse structured output", "raw": raw,
                    "stripped": stripped[:500]}


# ── Auto-select: API vs Ollama ────────────────────────────────────────
# When MINIMAX_API_KEY is set, replace OllamaClient with the API-backed
# version so all existing agent code (which imports OllamaClient) gets
# the fast external-API path without any import changes.

if os.environ.get("MINIMAX_API_KEY"):
    _ollama_base = OllamaClient
    OllamaClient = ApiClient
    logger.info("MINIMAX_API_KEY detected — agents will use API backend (%s)", os.environ.get("LLM_MODEL", "MiniMax-M2.7-highspeed"))


# ── Agent Base Class ─────────────────────────────────────────────────

@dataclass
class AgentContext:
    """Context passed through the agent's observe-reason-act cycle."""
    cycle: int = 0
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_result: Optional[dict] = None
    state: dict = field(default_factory=dict)


class Agent(ABC):
    """Base class for an AGI-driven agent with observe-reason-act loop.

    Subclasses implement observe(), reason(), and act(). The tick()
    method runs one full cycle.
    """

    def __init__(
        self,
        name: str,
        llm: Optional[OllamaClient] = None,
        backend=None,
        **kwargs,
    ):
        self.name = name
        self.llm = llm or OllamaClient()
        self.backend = backend
        self.context = AgentContext()
        self.config = kwargs
        # Self-heal: per-agent health tracker
        from empire_os.self_heal import HealthState
        self.health = HealthState()
        logger.info("Agent '%s' initialized (self-heal enabled)", self.name)

    @abstractmethod
    def observe(self) -> dict:
        """Gather all relevant state for reasoning."""
        ...

    @abstractmethod
    def reason(self, state: dict) -> str:
        """Use LLM to decide on an action. Returns a decision/plan string."""
        ...

    @abstractmethod
    def act(self, decision: str) -> dict:
        """Execute the decided action. Returns result dict."""
        ...

    def tick(self) -> dict:
        """Run one full observe-reason-act cycle with self-heal protection."""
        from empire_os.self_heal import safe_cycle, reset_state_if_stuck

        # Self-heal: if we've been failing too long, reset and try fresh
        reset_state_if_stuck(self.health, threshold=10)

        # Skip cycle if still in backoff from recent failure
        if self.health.should_skip_due_to_backoff():
            wait = self.health.in_backoff_until - time.time()
            logger.info("agent '%s' backing off for %.0fs", self.name, wait)
            # Skipped cycles still count as failures — agent is still broken
            self.health.record_failure(f"in_backoff ({wait:.0f}s remaining)")
            return {
                "cycle": self.context.cycle,
                "status": "skipped",
                "reason": f"in_backoff ({wait:.0f}s remaining)",
                "health": self._health_snapshot(),
            }

        self.context.cycle += 1
        t0 = time.time()

        def _run_cycle():
            state = self.observe()
            decision = self.reason(state)
            result = self.act(decision)
            return state, decision, result

        outcome = safe_cycle(_run_cycle, self.health)
        if outcome is None or not outcome.get("ok"):
            # Degraded — store and return
            self.context.last_result = outcome
            return outcome

        state, decision, result = outcome["value"]
        elapsed = time.time() - t0
        self.context.last_result = {
            "cycle": self.context.cycle,
            "elapsed": round(elapsed, 2),
            "state_summary": {k: v for k, v in state.items() if isinstance(v, (str, int, float, bool))},
            "decision_preview": decision[:120] if decision else "",
            "result": result,
            "health": self._health_snapshot(),
        }
        self.context.state.update(state)

        logger.info(
            "Agent '%s' cycle %d complete in %.1fs — %s",
            self.name, self.context.cycle, elapsed,
            result.get("summary", ""),
        )
        return self.context.last_result

    def _health_snapshot(self) -> dict:
        return {
            "consecutive_failures": self.health.consecutive_failures,
            "total_failures": self.health.total_failures,
            "total_recoveries": self.health.total_recoveries,
            "is_degraded": self.health.is_degraded,
            "last_error": self.health.last_error,
            "last_success_at": self.health.last_success_at,
        }

    def health_check(self) -> dict:
        """Public API for the dashboard / loop to inspect agent health."""
        return {
            "name": self.name,
            "cycle": self.context.cycle,
            **self._health_snapshot(),
        }
