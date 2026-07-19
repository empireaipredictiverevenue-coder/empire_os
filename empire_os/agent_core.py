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
        # reject response_format and return HTTP 400. The structured_chat
        # stripper already handles JSON-in-text, so we rely on that instead.
        if format == "json" and "openrouter.ai" not in self.base_url:
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


# ── Ollama-dead fallback → OpenRouter ────────────────────────────────
# The default OllamaClient points at a remote host (ornith-agent:11434)
# that is often unreachable from this box. If Ollama is down AND we have an
# OpenRouter key, transparently swap OllamaClient → OpenRouterClient so the
# observe-reason-act agents (growth, innovator, etc.) keep working without
# code changes. Uses a capable free model, not the code-only north-mini one.

_OR_FALLBACK_MODEL = os.environ.get("OR_FALLBACK_MODEL", "meta-llama/llama-3.1-8b-instruct:free")

def _ollama_reachable() -> bool:
    import urllib.request, urllib.error, socket
    try:
        req = urllib.request.Request("http://10.218.156.211:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False

if not os.environ.get("MINIMAX_API_KEY") and _load_openrouter_key() and not _ollama_reachable():
    _orig_ollama = OllamaClient
    class _OllamaToOpenRouter(OllamaClient):
        """Drop-in OllamaClient replacement backed by OpenRouter."""
        def __init__(self, base_url=None, model=None, timeout=60, **kw):
            self._or = OpenRouterClient(model=model or _OR_FALLBACK_MODEL, timeout=timeout)
            self.model = self._or.model
            self.timeout = timeout
        def chat(self, messages, system=None, temperature=0.3, format=None, **kw):
            return self._or.chat(messages, system=system, temperature=temperature)
        def structured_chat(self, messages, system=None, temperature=0.2, **kw):
            return self._or.structured_chat(messages, system=system, temperature=temperature)
    OllamaClient = _OllamaToOpenRouter
    logger.info("Ollama unreachable + OpenRouter key present — agents use OpenRouter (%s)", _OR_FALLBACK_MODEL)



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


# ── OpenRouter Client (North-mini, free tier) ──────────────────────
#
# North-mini = cohere/north-mini-code:free on OpenRouter. It is FREE but
# OpenRouter RATE-LIMITS the free tier (HTTP 429). This client handles that
# with exponential backoff + jitter so North-mini can "work freely" on a
# loop without silently dying. Key is read from
# /root/.empire_secrets/openrouter.env (600 perms), never hardcoded.

_OPENROUTER_ENV = Path("/root/.empire_secrets/openrouter.env")
_OPENROUTER_MODELS = {
    "north-mini": "cohere/north-mini-code:free",
    "north_mini": "cohere/north-mini-code:free",
}


def _load_openrouter_key() -> str:
    if _OPENROUTER_ENV.exists():
        try:
            for _ln in _OPENROUTER_ENV.read_text().splitlines():
                _ln = _ln.strip()
                if _ln.startswith("OPENROUTER_API_KEY="):
                    return _ln.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return os.environ.get("OPENROUTER_API_KEY", "")


class OpenRouterClient:
    """Free-tier OpenRouter client (North-mini). 429-safe via backoff."""

    def __init__(
        self,
        model: str = "cohere/north-mini-code:free",
        timeout: int = 60,
        max_retries: int = 5,
    ):
        self.model = _OPENROUTER_MODELS.get(model, model)
        self.api_key = _load_openrouter_key()
        self.timeout = timeout
        self.max_retries = max_retries
        self.base = "https://openrouter.ai/api/v1/chat/completions"

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Send a chat request. Returns text, or a JSON error object string
        on failure (so callers can detect + back off)."""
        if not self.api_key:
            return json.dumps({"error": "no_openrouter_key",
                               "fallback": True})
        if system:
            messages = [{"role": "system", "content": system}] + messages
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # Free tier: identify the app so OpenRouter can attribute.
            "transforms": ["middle-out"],
        }
        import urllib.request
        import urllib.error
        last_err = ""
        for attempt in range(self.max_retries):
            req = urllib.request.Request(
                self.base,
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://empire-ai.co.uk",
                    "X-Title": "Empire OS North-mini",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode())
                # Free tier can return HTTP 200 with EMPTY choices (rate-limit
                # / capacity shed). Treat empty content as a retryable error so
                # North-mini degrades gracefully instead of writing None.
                choices = data.get("choices") or []
                content = (choices[0].get("message", {}).get("content")
                           if choices else "") or ""
                if not content.strip():
                    last_err = "empty_content (free-tier capacity shed)"
                    wait = min(2 ** attempt * 5 + attempt, 120)
                    logger.warning("North-mini %s — retry %ss",
                                  last_err, wait)
                    time.sleep(wait)
                    continue
                return content
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, "read") else ""
                if e.code == 429:
                    # Rate limited — back off exponentially.
                    wait = min(2 ** attempt * 5 + attempt, 120)
                    logger.warning(
                        "North-mini 429 (rate limit) — backoff %ss "
                        "(attempt %d/%d)", wait, attempt + 1, self.max_retries)
                    time.sleep(wait)
                    last_err = f"429 rate_limit (attempt {attempt+1})"
                    continue
                last_err = f"HTTP {e.code}: {body[:200]}"
                logger.warning("North-mini HTTP error: %s", last_err)
                break
            except (urllib.error.URLError, OSError, ValueError,
                    KeyError, IndexError) as e:
                # network / JSON / shape errors -> retry or report
                last_err = f"{type(e).__name__}: {e!r}"[:300]
                wait = min(2 ** attempt * 5, 120)
                logger.warning("North-mini transient error: %s — retry %ss",
                              last_err, wait)
                time.sleep(wait)
        return json.dumps({"error": last_err or "unknown", "fallback": True})

    def structured_chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> dict:
        raw = self.chat(messages, system=system, temperature=temperature)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"error": "parse_failed", "raw": raw}


class OpenCodeZenClient:
    """OpenAI-compatible client for OpenCode Zen (free-tier deepseek etc).

    Base: https://opencode.ai/zen/v1  (chat/completions)
    Key:  /root/.empire_secrets/opencode_zen.env (OPENCODE_ZEN_API_KEY)
    Same chat() interface + 429/empty-content backoff as OpenRouterClient.
    Free tier (deepseek-v4-flash-free) is rate-limited; degrade gracefully.
    """

    def __init__(self, model: Optional[str] = None,
                 api_key: Optional[str] = None,
                 base: Optional[str] = None,
                 max_retries: int = 5, timeout: int = 45):
        p = Path("/root/.empire_secrets/opencode_zen.env")
        env = {}
        if p.exists():
            for ln in p.read_text().splitlines():
                if "=" in ln and not ln.startswith("#"):
                    k, v = ln.split("=", 1)
                    env[k.strip()] = v.strip()
        self.api_key = api_key or env.get("OPENCODE_ZEN_API_KEY")
        self.base = (base or env.get("OPENCODE_ZEN_BASE")
                     or "https://opencode.ai/zen/v1") + "/chat/completions"
        self.model = model or "deepseek-v4-flash-free"
        self.max_retries = max_retries
        self.timeout = timeout
        if not self.api_key:
            logger.warning("OpenCodeZenClient: no API key loaded")

    def chat(self, messages: list[dict], system: Optional[str] = None,
             temperature: float = 0.2, max_tokens: int = 800,
             format: str = "text") -> Optional[str]:
        if not self.api_key:
            return None
        if system:
            messages = [{"role": "system", "content": system}] + messages
        payload = {"model": self.model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens}
        last_err = ""
        import urllib.request
        import urllib.error
        for attempt in range(self.max_retries):
            req = urllib.request.Request(
                self.base,
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json",
                         "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                                       "Chrome/120.0 Safari/537.36"},
                method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode())
                choices = data.get("choices") or []
                content = (choices[0].get("message", {}).get("content")
                           if choices else "") or ""
                if not content.strip():
                    last_err = "empty_content (free-tier capacity shed)"
                    wait = min(2 ** attempt * 5 + attempt, 120)
                    logger.warning("Zen %s — retry %ss", last_err, wait)
                    time.sleep(wait)
                    continue
                return content
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, "read") else ""
                last_err = f"HTTP {e.code}: {body[:200]}"
                if e.code == 429:
                    wait = min(2 ** attempt * 10 + attempt * 2, 120)
                    logger.warning("Zen 429 — backoff %ss", wait)
                    time.sleep(wait)
                    continue
                logger.warning("Zen HTTP error: %s", last_err)
                break
            except (urllib.error.URLError, OSError, ValueError,
                    json.JSONDecodeError, KeyError) as e:
                last_err = f"{type(e).__name__}: {e}"
                wait = min(2 ** attempt * 4 + attempt, 90)
                logger.warning("Zen transient %s — retry %ss", last_err, wait)
                time.sleep(wait)
                continue
        return json.dumps({"error": "zen_failed", "detail": last_err[:200]})

    def structured_chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.2,
    ) -> dict:
        """Mirror OpenRouterClient.structured_chat: chat then parse JSON.

        agi_scout / agi_marketing / synthetic_intelligence call
        self.llm.structured_chat(...) — OpenCodeZenClient must provide it
        or those agents crash with AttributeError (seen in code-review
        synthetic generation)."""
        raw = self.chat(messages, system=system, temperature=temperature)
        if raw is None:
            return {"error": "zen_no_key"}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"error": "parse_failed", "raw": raw}

