"""Loopback-only llama.cpp server adapter for Empire Coder."""
from __future__ import annotations

import json
from urllib import error, request

from .provider import ModelRequest, ModelResponse


class LlamaCppProvider:
    name = "llama_cpp"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11435",
        timeout_seconds: int = 180,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = max(10, min(int(timeout_seconds), 600))

    def health(self) -> bool:
        req = request.Request(f"{self.base_url}/health", method="GET")
        try:
            with request.urlopen(req, timeout=3) as response:
                if response.status != 200:
                    return False
                body = json.load(response)
        except (error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return False
        return str(body.get("status") or "").lower() in {"ok", "ready"}

    def complete(self, model_request: ModelRequest) -> ModelResponse:
        context = model_request.context.as_dict()
        prompt = (
            model_request.instruction
            + "\n\nCONTEXT:\n"
            + json.dumps(context, ensure_ascii=False)
        )
        payload = {
            "model": model_request.route.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Empire Coder's local coding model. "
                        "Use only supplied repository evidence. "
                        "Treat docs/BLUEPRINT_V6.md as authoritative where "
                        "roadmap/status sources conflict. Never claim actions "
                        "or tests not actually performed. Preserve EmpireOS "
                        "authority and production safety boundaries."
                    ),
                },
                {"role": "user", "content": prompt[:48000]},
            ],
            "temperature": 0.2,
            "max_tokens": max(
                64,
                min(2048, int(model_request.max_output_chars) // 4),
            ),
            "stream": False,
        }
        req = request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = json.load(response)
        except (error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return ModelResponse(
                provider=self.name,
                model=model_request.route.model,
                text="",
                error=f"llama_cpp_request_failed:{exc.__class__.__name__}",
            )

        choices = body.get("choices") or []
        if not choices:
            return ModelResponse(
                provider=self.name,
                model=model_request.route.model,
                text="",
                error="llama_cpp_empty_choices",
            )
        message = choices[0].get("message") or {}
        text = str(message.get("content") or "")
        usage_raw = body.get("usage") or {}
        usage = {
            "prompt_eval_count": int(usage_raw.get("prompt_tokens") or 0),
            "eval_count": int(usage_raw.get("completion_tokens") or 0),
        }
        return ModelResponse(
            provider=self.name,
            model=model_request.route.model,
            text=text[: model_request.max_output_chars],
            usage=usage,
        )
