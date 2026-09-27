"""Empire OS thin LLM execution gateway.

The gateway executes an already-selected route. It does not contain the
business policy for choosing a provider/model.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional
from pathlib import Path

from empire_os.model_registry import ModelRegistry
from empire_os.model_router import ModelRouter, RouteDecision

logger = logging.getLogger("llm_gateway")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class GatewayError(RuntimeError):
    pass


class GeminiClient:
    """Minimal Gemini generateContent adapter.

    The API key is read from /etc/empire_os/llm_secrets/gemini.env or GEMINI_API_KEY.
    """

    def __init__(
        self,
        model: str = "gemini-3.8-flash",
        timeout: int = 60,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.api_key = self._load_key()
        self.base = (
            "https://generativelanguage.googleapis.com/v1/models/"
            f"{self.model}:generateContent"
        )

    @staticmethod
    def _load_key() -> str:
        path = "/etc/empire_os/llm_secrets/gemini.env"
        try:
            text = Path(path).read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
        return os.environ.get("GEMINI_API_KEY", "")

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        import urllib.error
        import urllib.request

        if not self.api_key:
            return json.dumps({
                "error": "no_gemini_key",
                "fallback": True,
            })

        contents = []
        if system:
            contents.append({
                "role": "user",
                "parts": [{"text": system}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood."}],
            })

        for message in messages:
            role = message.get("role", "user")
            if role == "assistant":
                role = "model"
            elif role not in {"user", "model"}:
                role = "user"

            content = str(message.get("content", ""))
            contents.append({
                "role": role,
                "parts": [{"text": content}],
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        req = urllib.request.Request(
            self.base,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            return json.dumps({
                "error": f"gemini_request_failed:{exc}",
                "fallback": True,
            })

        candidates = data.get("candidates") or []
        if not candidates:
            return json.dumps({
                "error": "gemini_empty_candidates",
                "fallback": True,
            })

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(
            str(part.get("text", ""))
            for part in parts
            if isinstance(part, dict) and "text" in part
        )

        return text


class LLMGateway:
    """Execution facade behind the registry/router."""

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        router: ModelRouter | None = None,
    ) -> None:
        self.registry = registry or ModelRegistry()
        self.router = router or ModelRouter(self.registry)
        self.calls = 0
        self.failures = 0

    def policy(self, task: str) -> tuple[str, str]:
        """Compatibility shim.

        New callers should use route(). The compatibility method now resolves
        through the registry instead of the old TASK_ENV task map.
        """
        decision = self.router.route(
            task=task,
            messages=[],
            system=None,
        )
        return decision.model.provider, decision.model.model

    def route(
        self,
        messages: list[dict[str, Any]],
        *,
        task: str = "reasoning",
        system: Optional[str] = None,
        stakes: str = "normal",
        require_reasoning: bool = False,
        require_vision: bool = False,
        budget_remaining: float | None = None,
        remaining_queries: int | None = None,
    ) -> RouteDecision:
        return self.router.route(
            task=task,
            messages=messages,
            system=system,
            stakes=stakes,
            require_reasoning=require_reasoning,
            require_vision=require_vision,
            budget_remaining=budget_remaining,
            remaining_queries=remaining_queries,
        )

    def describe(self) -> dict:
        return {
            "models": self.registry.describe(),
            "providers": self.registry.providers(),
        }

    def _client(self, provider: str, model: str, timeout: int):
        from empire_os.agent_core import (
            OllamaClient,
            OpenRouterClient,
            OpenCodeZenClient,
            ApiClient,
        )

        provider = provider.lower()

        if provider == "ollama":
            return OllamaClient(
                model=model or _env("OLLAMA_MODEL", "qwen2.5:7b"),
                timeout=timeout,
            )

        if provider == "openrouter":
            return OpenRouterClient(
                model=model or _env(
                    "OPENROUTER_MODEL",
                    "cohere/north-mini-code:free",
                ),
                timeout=timeout,
            )

        if provider in {"opencode", "opencode_zen", "zen"}:
            return OpenCodeZenClient(
                model=model or _env(
                    "OPENCODE_ZEN_MODEL",
                    "deepseek-v4-flash-free",
                ),
                timeout=timeout,
            )

        if provider in {"api", "openai_compatible"}:
            base_url = _env("LLM_BASE_URL")
            api_key = _env("LLM_API_KEY") or _env("OPENAI_API_KEY")
            return ApiClient(
                base_url=base_url,
                model=model or _env("LLM_MODEL"),
                timeout=timeout,
                api_key=api_key,
            )

        if provider in {"gemini", "google", "google_gemini"}:
            return GeminiClient(
                model=model or _env("GEMINI_MODEL", "gemini-3.8-flash"),
                timeout=timeout,
            )

        raise GatewayError(f"unknown_llm_provider:{provider}")

    def chat(
        self,
        messages: list[dict],
        *,
        task: str = "reasoning",
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        stakes: str = "normal",
        require_reasoning: bool = False,
        require_vision: bool = False,
        budget_remaining: float | None = None,
        remaining_queries: int | None = None,
    ) -> str:
        decision = self.route(
            messages,
            task=task,
            system=system,
            stakes=stakes,
            require_reasoning=require_reasoning,
            require_vision=require_vision,
            budget_remaining=budget_remaining,
            remaining_queries=remaining_queries,
        )

        provider = decision.model.provider
        model = decision.model.model
        timeout = int(_env("EMPIRE_LLM_TIMEOUT", "60"))
        attempts = int(_env("EMPIRE_LLM_RETRIES", "2"))

        last_error = ""

        for attempt in range(attempts + 1):
            self.calls += 1

            try:
                client = self._client(provider, model, timeout)
                kwargs = {
                    "messages": messages,
                    "system": system,
                    "temperature": temperature,
                }

                if provider.lower() in {"openrouter", "opencode", "opencode_zen", "zen"}:
                    kwargs["max_tokens"] = max_tokens

                started = time.monotonic()
                result = client.chat(**kwargs)
                latency_ms = round((time.monotonic() - started) * 1000, 1)

                if result is None or not str(result).strip():
                    raise GatewayError("empty_llm_response")

                # Provider adapters may return {"error": ...} as a string
                # instead of raising. Never record those as successful calls.
                result_text = str(result).strip()
                try:
                    parsed_result = json.loads(result_text)
                except (json.JSONDecodeError, TypeError):
                    parsed_result = None

                if isinstance(parsed_result, dict) and parsed_result.get("error"):
                    raise GatewayError(
                        f"provider_error:{parsed_result.get('error')}"
                    )

                self._receipt(
                    task=task,
                    route=decision.route,
                    provider=provider,
                    model=getattr(client, "model", model),
                    score=decision.score,
                    reasoning_gain=decision.reasoning_gain,
                    estimated_cost=decision.estimated_cost,
                    ok=True,
                    attempt=attempt + 1,
                    latency_ms=latency_ms,
                )
                return str(result)

            except Exception as exc:
                self.failures += 1
                last_error = f"{type(exc).__name__}: {exc}"

                self._receipt(
                    task=task,
                    route=decision.route,
                    provider=provider,
                    model=model,
                    score=decision.score,
                    reasoning_gain=decision.reasoning_gain,
                    estimated_cost=decision.estimated_cost,
                    ok=False,
                    attempt=attempt + 1,
                    latency_ms=latency_ms if "latency_ms" in locals() else None,
                    error=last_error[:300],
                )

                if attempt < attempts:
                    delay = min(2 ** attempt, 8)
                    logger.warning(
                        "LLM failure task=%s provider=%s model=%s attempt=%d/%d; "
                        "retry in %ss: %s",
                        task,
                        provider,
                        model,
                        attempt + 1,
                        attempts + 1,
                        delay,
                        last_error[:160],
                    )
                    time.sleep(delay)

        raise GatewayError(last_error or "llm_failed")

    def structured_chat(
        self,
        messages: list[dict],
        *,
        task: str = "reasoning",
        system: Optional[str] = None,
        temperature: float = 0.2,
        stakes: str = "normal",
    ) -> dict:
        raw = self.chat(
            messages,
            task=task,
            system=system,
            temperature=temperature,
            stakes=stakes,
        )

        cleaned = raw.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "error": "structured_parse_failed",
                "raw": raw[:4000],
            }

    def _receipt(
        self,
        *,
        task: str,
        route: str,
        provider: str,
        model: str,
        score: float,
        reasoning_gain: float,
        estimated_cost: float,
        ok: bool,
        attempt: int,
        latency_ms: float | None = None,
        error: str = "",
    ) -> None:
        path = _env(
            "LLM_RECEIPT_PATH",
            "/srv/empire_os/runtime/llm/receipts.jsonl",
        )

        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            event = {
                "ts": time.time(),
                "task": task,
                "route": route,
                "provider": provider,
                "model": model or "(default)",
                "router_score": score,
                "reasoning_gain_prior": reasoning_gain,
                "estimated_cost": estimated_cost,
                "ok": ok,
                "attempt": attempt,
                "latency_ms": latency_ms,
            }

            if error:
                event["error"] = error

            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event) + "\n")

        except Exception:
            logger.exception("failed to write llm receipt")


gateway = LLMGateway()
