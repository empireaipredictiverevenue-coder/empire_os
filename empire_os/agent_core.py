#!/usr/bin/env python3
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
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("agent_core")


# ── Base Agent Class ──────────────────────────────────────────────────
# This is the base class that all Empire agents extend (SyntheticAgent,
# AgiScoutAgent, etc.). It provides the observe/reason/act cycle with
# self-heal protection and health monitoring.

@dataclass
class AgentContext:
    """Context passed through the agent's observe-reason-act cycle."""
    cycle: int = 0
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_result: Optional[dict] = None
    state: dict = field(default_factory=dict)


class Agent(ABC):
    """Base class for an AGI-driven agent with observe-reason-act loop.

    Subclasses implement observe(), reason(), and act(). The tick() method
    runs one full cycle with self-heal protection.
    """

    def __init__(
        self,
        name: str,
        llm: Optional[OllamaClient] = None,
        backend=None,
        **kwargs,
    ):
        self.name = name
        # Rule-based mode: never connect to Ollama (dead host = wasted cycles + spam).
        if llm is False:
            self.llm = None
        elif llm is None:
            self.llm = OllamaClient()
        else:
            self.llm = llm
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
        hs = self.health
        return {
            "consecutive_failures": hs.consecutive_failures,
            "total_failures": hs.total_failures,
            "total_recoveries": hs.total_recoveries,
            "is_degraded": hs.is_degraded,
            "last_error": hs.last_error,
            "last_success_at": hs.last_success_at,
        }

    def health_check(self) -> dict:
        """Public API for the dashboard / loop to inspect agent health."""
        return {
            "name": self.name,
            "cycle": self.context.cycle,
            **self._health_snapshot(),
        }


# ── Ollama LLM Client ────────────────────────────────────────────────

class OllamaClient:
    """Lightweight client for Ollama — uses env OLLAMA_HOST or defaults to localhost:11434."""

    def __init__(
        self,
        base_url: str = "",
        model: str = "",
        timeout: int = 30,
    ):
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
        # Use OLLAMA_MODEL for local ollama, fall back to LLM_MODEL for cross-compat,
        # then hard default
        self.model = model or os.environ.get("OLLAMA_MODEL") or os.environ.get("LLM_MODEL") or "qwen2.5:3b"
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
        format: Optional[str] = None,  # ignored, for OllamaClient compatibility
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
        # When an OpenRouter key is present, it fully takes over (reachable,
        # paid+free tiers). MiniMax is only used when OpenRouter is absent.
        if os.environ.get("OPENROUTER_API_KEY"):
            self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
            base_url = base_url or "https://openrouter.ai/api/v1"
            # Force a known-good OpenRouter model (env LLM_MODEL may point at
            # MiniMax and be inherited from a systemd Environment= override).
            model = model or "openai/gpt-4o-mini"
        else:
            self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
            # When MINIMAX is configured, any passed Ollama URL is ignored
            if self.api_key and base_url and ("localhost" in base_url or "11434" in base_url or "ollama" in base_url.lower()):
                base_url = ""
            base_url = base_url or os.environ.get("LLM_BASE_URL", "https://api.minimax.io/v1")
            model = model or os.environ.get("LLM_MODEL", "MiniMax-M2.7-highspeed")
        self.base_url = base_url.rstrip("/")
        self.model = model
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
        # Only force JSON mode when NOT on OpenRouter free-tier models, which
        # reject response_format and return HTTP 400. Also skip for MiniMax
        # which doesn't support response_format. The structured_chat
        # stripper already handles JSON-in-text, so we rely on that instead.
        if format == "json" and "openrouter.ai" not in self.base_url and "minimax" not in self.base_url:
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
        format: Optional[str] = None,  # ignored, for OllamaClient compatibility
    ) -> dict:
        """Chat with JSON-structured output guaranteed."""
        raw = self.chat(
            messages=messages,
            system=system,
            temperature=temperature,
            format="json",
        )
        # Strip <thinking>...</thinking> blocks that some models emit
        import re as _re
        stripped = _re.sub(r'<.*?thinking.*?>.*?</.*?>', '', raw, flags=_re.DOTALL).strip()
        # Strip Markdown code fences (```json ... ```, ``` ... ```)
        stripped = _re.sub(r'^```\w*\s*', '', raw).strip()
        stripped = _re.sub(r'\s*```$', '', stripped).strip()
        # If all that's left isn't JSON, try to find a JSON object in it
        stripped = _re.sub(r'^[^{]*', '', stripped).strip()  # drop leading non-JSON
        stripped = _re.sub(r'[^}]*$', '', stripped).strip()  # drop trailing non-JSON
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            return {"error": "Failed to parse structured output", "raw": raw,
                    "stripped": stripped[:500]}


_OR_FALLBACK_MODEL = os.environ.get("OR_FALLBACK_MODEL", "meta-llama/llama-3.1-8b-instruct:free")

def _ollama_reachable(host: str = "") -> bool:
    """Check if an Ollama instance is reachable at the given host or env default."""
    import urllib.request, urllib.error, socket
    base = (host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
    try:
        req = urllib.request.Request(f"{base}/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


# ── Auto-select: API vs Ollama ────────────────────────────────────────
# Priority:
# 0. If OLLAMA_HOST is explicitly set AND ollama is reachable, use local Ollama.
# 1. OPENROUTER_API_KEY → OpenRouter (GPT-4o-mini)
# 2. GOOGLE_API_KEY → Gemini (gemini-1.5-pro)
# 3. MINIMAX_API_KEY → MiniMax (M2.7-highspeed)
# 4. Ollama fallback (no API keys, no settings)

# 0. Local Ollama wins if OLLAMA_HOST is set and reachable
_ollama_configured = os.environ.get("OLLAMA_HOST")
if _ollama_configured and _ollama_reachable():
    logger.info("OLLAMA_HOST=%s reachable — agents will use local Ollama (%s)",
                 _ollama_configured, os.environ.get("LLM_MODEL", "default"))
elif os.environ.get("OPENROUTER_API_KEY"):
    _ollama_base = OllamaClient
    OllamaClient = ApiClient
    logger.info("OPENROUTER_API_KEY detected — agents will use OpenRouter (%s)", os.environ.get("OR_FALLBACK_MODEL", "openai/gpt-4o-mini"))

# 2. Google Gemini
elif os.environ.get("GOOGLE_API_KEY"):
    try:
        import google.generativeai as genai

        class GeminiClient:
            """Google Gemini API client (gemini-1.5-pro)."""

            def __init__(
                self,
                base_url: str = "",
                model: str = "",
                timeout: int = 30,
                api_key: str = "",
            ):
                api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(model or os.environ.get("LLM_MODEL", "gemini-1.5-pro"))
                self.timeout = timeout

            def _post(self, payload: dict) -> dict:
                """Not used for Gemini - we use the SDK directly."""
                return {"error": "Not implemented for Gemini"}

            def chat(
                self,
                messages: list[dict],
                system: Optional[str] = None,
                temperature: float = 0.3,
                format: Optional[str] = None,
            ) -> str:
                """Send a chat request and return the response text."""
                # Convert to Gemini format
                contents = []
                if system:
                    contents.append({"role": "user", "parts": [system]})
                    contents.append({"role": "model", "parts": ["Understood."]})

                for msg in messages:
                    role = "user" if msg["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [msg["content"]]})

                try:
                    response = self.model.generate_content(
                        contents,
                        generation_config=genai.types.GenerationConfig(
                            temperature=temperature,
                            max_output_tokens=4096,
                            response_mime_type="application/json" if format == "json" else "text/plain",
                        ),
                    )
                    return response.text
                except Exception as e:
                    logger.warning("Gemini call failed: %s", e)
                    return json.dumps({"error": str(e), "fallback": True})

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
                import re as _re
                stripped = _re.sub(r'```\w*\s*', '', raw).strip()
                stripped = _re.sub(r'\s*```$', '', stripped).strip()
                stripped = _re.sub(r'^[^{]*', '', stripped).strip()
                stripped = _re.sub(r'[^}]*$', '', stripped).strip()
                try:
                    return json.loads(stripped)
                except (json.JSONDecodeError, TypeError):
                    return {"error": "Failed to parse structured output", "raw": raw}

        _ollama_base = OllamaClient
        OllamaClient = GeminiClient
        logger.info("GOOGLE_API_KEY detected — agents will use Gemini (%s)", os.environ.get("LLM_MODEL", "gemini-1.5-pro"))

    except ImportError:
        logger.warning("google-generativeai not installed, skipping Gemini — will try next provider")
        pass

# 3. MiniMax
elif os.environ.get("MINIMAX_API_KEY"):
    _ollama_base = OllamaClient
    OllamaClient = ApiClient
    logger.info("MINIMAX_API_KEY detected — agents will use API backend (%s)", os.environ.get("LLM_MODEL", "MiniMax-M2.7-highspeed"))

# 4. Ollama fallback (no API keys set)
else:
    logger.info("No API keys set — agents will use Ollama fallback")


# ── OpenRouter Client (alias for ApiClient when OPENROUTER_API_KEY is set) ─────
# OpenRouterClient is an alias for ApiClient when OPENROUTER_API_KEY is detected
# This provides a named export for imports like "from empire_os.agent_core import OpenRouterClient"
OpenRouterClient = ApiClient
logger.debug("OpenRouterClient alias created for ApiClient")


# ── Ollama-dead fallback → OpenRouter ────────────────────────────────
# Safety net: if the local Ollama goes down mid-session (e.g. OOM restart)
# and we have an OpenRouter key, transparently swap to avoid outages.

if not _ollama_reachable() and os.environ.get("OPENROUTER_API_KEY"):
    _ollama_base = OllamaClient
    OllamaClient = OpenRouterClient
    logger.info("Ollama unreachable — falling back to OpenRouter (%s)", _OR_FALLBACK_MODEL)