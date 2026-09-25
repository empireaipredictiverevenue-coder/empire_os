"""Promptfoo provider for an OpenAI-compatible Empire/local model endpoint."""
from __future__ import annotations

import json
import os
import urllib.request


def call_api(prompt, options, context):
    config = dict((options or {}).get("config") or {})
    url = (
        os.getenv("EMPIRE_EVAL_URL")
        or config.get("url")
        or "http://127.0.0.1:11435/v1/chat/completions"
    )
    model = (
        os.getenv("EMPIRE_EVAL_MODEL")
        or config.get("model")
        or "qwen2.5-coder:1.5b"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": str(prompt)}],
        "temperature": 0,
        "max_tokens": int(config.get("max_tokens", 300)),
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("EMPIRE_EVAL_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return {"error": "eval provider returned no choices"}
    message = choices[0].get("message") or {}
    output = str(message.get("content") or "")
    if not output:
        return {"error": "eval provider returned empty content"}
    return {"output": output}
