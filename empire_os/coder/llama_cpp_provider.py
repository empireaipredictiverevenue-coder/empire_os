"""Loopback-only llama.cpp server adapter for EmpireOS.

Canonical llama.cpp adapter shared by Empire Coder and the provider-neutral
LLMGateway. This provider performs inference only after an upstream caller has
selected it; it grants no routing, commercial, payment, or action authority.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from urllib import error, request

from .provider import ModelRequest, ModelResponse


class LlamaCppProvider:
    """OpenAI-compatible adapter for Empire's loopback llama.cpp runtime."""

    name = "llama_cpp"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11435",
        timeout_seconds: int = 180,
        model: str = "qwen2.5-coder:1.5b",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = max(
            10,
            min(int(timeout_seconds), 600),
        )
        self.model = (
            str(model).strip()
            or "qwen2.5-coder:1.5b"
        )

    def health(self) -> bool:
        req = request.Request(
            f"{self.base_url}/health",
            method="GET",
        )

        try:
            with request.urlopen(
                req,
                timeout=3,
            ) as response:
                if response.status != 200:
                    return False
                body = json.load(response)
        except (
            error.URLError,
            error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
        ):
            return False

        return str(
            body.get("status") or ""
        ).lower() in {
            "ok",
            "ready",
        }

    def _completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        payload = {
            "model": (
                str(model).strip()
                or self.model
            ),
            "messages": [
                dict(message)
                for message in messages
            ],
            "temperature": float(temperature),
            "max_tokens": max(
                1,
                min(int(max_tokens), 8192),
            ),
            "stream": False,
        }

        req = request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(
                req,
                timeout=self.timeout_seconds,
            ) as response:
                body = json.load(response)
        except (
            error.URLError,
            error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
        ) as exc:
            return {
                "error": (
                    "llama_cpp_request_failed:"
                    f"{exc.__class__.__name__}"
                )
            }

        if not isinstance(body, dict):
            return {
                "error": "llama_cpp_invalid_response"
            }

        return body

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """Provider-neutral chat surface used by LLMGateway."""

        normalized = [
            dict(message)
            for message in messages
        ]

        if system:
            normalized = [
                {
                    "role": "system",
                    "content": system,
                },
                *normalized,
            ]

        body = self._completion(
            model=self.model,
            messages=normalized,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if body.get("error"):
            return json.dumps(
                {"error": body["error"]},
                sort_keys=True,
            )

        choices = body.get("choices") or []

        if not choices:
            return json.dumps(
                {
                    "error":
                    "llama_cpp_empty_choices"
                },
                sort_keys=True,
            )

        message = choices[0].get(
            "message"
        ) or {}

        text = str(
            message.get("content") or ""
        ).strip()

        if not text:
            return json.dumps(
                {
                    "error":
                    "llama_cpp_empty_content"
                },
                sort_keys=True,
            )

        return text

    def complete(
        self,
        model_request: ModelRequest,
    ) -> ModelResponse:
        """Established Empire Coder ModelRequest contract."""

        context = (
            model_request.context.as_dict()
        )

        prompt = (
            model_request.instruction
            + "\n\nCONTEXT:\n"
            + json.dumps(
                context,
                ensure_ascii=False,
            )
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Empire Coder's local coding model. "
                    "Use only supplied repository evidence. "
                    "Treat docs/BLUEPRINT_V6.md as authoritative "
                    "where roadmap/status sources conflict. "
                    "Never claim actions or tests not actually "
                    "performed. Preserve EmpireOS authority and "
                    "production safety boundaries."
                ),
            },
            {
                "role": "user",
                "content": prompt[:48000],
            },
        ]

        body = self._completion(
            model=model_request.route.model,
            messages=messages,
            temperature=0.2,
            max_tokens=max(
                64,
                min(
                    2048,
                    int(
                        model_request.max_output_chars
                    ) // 4,
                ),
            ),
        )

        if body.get("error"):
            return ModelResponse(
                provider=self.name,
                model=model_request.route.model,
                text="",
                error=str(body["error"]),
            )

        choices = body.get("choices") or []

        if not choices:
            return ModelResponse(
                provider=self.name,
                model=model_request.route.model,
                text="",
                error="llama_cpp_empty_choices",
            )

        message = (
            choices[0].get("message")
            or {}
        )

        text = str(
            message.get("content") or ""
        )

        usage_raw = (
            body.get("usage")
            or {}
        )

        usage = {
            "prompt_eval_count": int(
                usage_raw.get(
                    "prompt_tokens"
                ) or 0
            ),
            "eval_count": int(
                usage_raw.get(
                    "completion_tokens"
                ) or 0
            ),
        }

        return ModelResponse(
            provider=self.name,
            model=model_request.route.model,
            text=text[
                :model_request.max_output_chars
            ],
            usage=usage,
        )
