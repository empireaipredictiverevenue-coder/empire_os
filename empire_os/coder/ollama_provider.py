"""Local Ollama model-provider adapter for Empire Coder."""
from __future__ import annotations

import json
from urllib import error, request

from .provider import ModelRequest, ModelResponse


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: int = 600,
        context_length: int = 16384,
        num_threads: int | None = None,
        think: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.context_length = max(4096, min(int(context_length), 65536))
        self.num_threads = num_threads
        self.think = bool(think)

    def complete(self, model_request: ModelRequest) -> ModelResponse:
        context = model_request.context.as_dict()
        max_prompt_chars = max(
            8_000,
            min(self.context_length * 3, 96_000),
        )
        max_predict = max(
            64,
            min(2048, model_request.max_output_chars // 4),
        )
        options = {
            "temperature": 0.2,
            "num_ctx": self.context_length,
            "num_predict": max_predict,
        }
        if self.num_threads is not None:
            options["num_thread"] = int(self.num_threads)
        payload = {
            "model": model_request.route.model,
            "stream": False,
            "think": self.think,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Empire Coder's local coding model. "
                        "Use only supplied repository evidence. "
                        "Treat docs/BLUEPRINT_V6.md as authoritative when "
                        "roadmap or implementation status conflicts with "
                        "another repository source. "
                        "Do not claim actions or tests you did not perform. "
                        "Do not propose production-changing actions without "
                        "an explicit human approval gate."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        model_request.instruction
                        + "\n\nCONTEXT:\n"
                        + json.dumps(context, ensure_ascii=False)
                    )[:max_prompt_chars],
                },
            ],
            "options": options,
            "keep_alive": "10m",
        }
        req = request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(
                req,
                timeout=self.timeout_seconds,
            ) as response:
                body = json.load(response)
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return ModelResponse(
                provider=self.name,
                model=model_request.route.model,
                text="",
                error=f"ollama_request_failed:{exc.__class__.__name__}",
            )

        message = body.get("message") or {}
        text = str(message.get("content") or "")
        usage = {
            "prompt_eval_count": int(body.get("prompt_eval_count") or 0),
            "eval_count": int(body.get("eval_count") or 0),
        }
        return ModelResponse(
            provider=self.name,
            model=model_request.route.model,
            text=text[: model_request.max_output_chars],
            usage=usage,
        )

    def models(self) -> tuple[str, ...]:
        req = request.Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with request.urlopen(req, timeout=5) as response:
                body = json.load(response)
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return ()
        names = []
        for row in body.get("models") or []:
            name = str(row.get("name") or "").strip()
            if name:
                names.append(name)
        return tuple(sorted(set(names)))

    def has_model(self, model: str) -> bool:
        return str(model).strip() in self.models()

    def health(self) -> bool:
        req = request.Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except (error.URLError, TimeoutError):
            return False
