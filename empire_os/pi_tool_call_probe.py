"""Direct structured tool-call probe for the local llama.cpp coding lane.

This probe never executes a tool. It verifies only that the OpenAI-compatible
endpoint returns a real assistant.message.tool_calls structure that Pi can
consume safely.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from urllib import request
from typing import Any

DEFAULT_URL = "http://127.0.0.1:11435/v1/chat/completions"
DEFAULT_MODEL = "qwen2.5-coder:1.5b"


@dataclass(frozen=True)
class ToolCallProbeResult:
    ok: bool
    reason: str
    model: str
    tool_call_count: int
    tool_name: str | None
    arguments_valid_json: bool
    raw_content_present: bool
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_tool_call_payload(
    payload: dict[str, Any],
    *,
    expected_tool: str,
    model: str,
) -> ToolCallProbeResult:
    choices = payload.get("choices") or []
    message = ((choices[0] if choices else {}).get("message") or {}) if isinstance(choices, list) else {}
    tool_calls = message.get("tool_calls") or []
    content = message.get("content")
    if not isinstance(tool_calls, list) or not tool_calls:
        return ToolCallProbeResult(
            ok=False,
            reason="structured_tool_calls_missing",
            model=model,
            tool_call_count=0,
            tool_name=None,
            arguments_valid_json=False,
            raw_content_present=bool(str(content or "").strip()),
        )

    first = tool_calls[0] if isinstance(tool_calls[0], dict) else {}
    fn = first.get("function") or {}
    name = str(fn.get("name") or "").strip() or None
    raw_args = fn.get("arguments")
    args_ok = False
    if isinstance(raw_args, str):
        try:
            args_ok = isinstance(json.loads(raw_args), dict)
        except json.JSONDecodeError:
            args_ok = False
    elif isinstance(raw_args, dict):
        args_ok = True

    return ToolCallProbeResult(
        ok=(name == expected_tool and args_ok),
        reason=("structured_tool_call_ready" if name == expected_tool and args_ok else "structured_tool_call_invalid"),
        model=model,
        tool_call_count=len(tool_calls),
        tool_name=name,
        arguments_valid_json=args_ok,
        raw_content_present=bool(str(content or "").strip()),
    )


def probe_local_tool_calls(
    *,
    url: str = DEFAULT_URL,
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 30,
) -> ToolCallProbeResult:
    expected_tool = "empire_probe"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return exactly one function call when a tool is available. Do not answer with prose or raw JSON."},
            {"role": "user", "content": "Call empire_probe with value TOOL_CALL_OK."},
        ],
        "tools": [{
            "type": "function",
            "function": {
                "name": expected_tool,
                "description": "Capability probe. Performs no action.",
                "parameters": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
            },
        }],
        "tool_choice": {"type": "function", "function": {"name": expected_tool}},
        "temperature": 0,
        "max_tokens": 96,
        "stream": False,
    }
    req = request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer local-only"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=max(1, timeout_seconds)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return ToolCallProbeResult(
            ok=False, reason=f"transport_error:{type(exc).__name__}", model=model,
            tool_call_count=0, tool_name=None, arguments_valid_json=False,
            raw_content_present=False,
        )
    if not isinstance(payload, dict):
        return ToolCallProbeResult(
            ok=False, reason="invalid_response_shape", model=model,
            tool_call_count=0, tool_name=None, arguments_valid_json=False,
            raw_content_present=False,
        )
    return evaluate_tool_call_payload(payload, expected_tool=expected_tool, model=model)
