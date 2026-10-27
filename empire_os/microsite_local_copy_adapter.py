"""Optional localhost-only copy draft pass using existing EmpireOS llama.cpp.

An inference response is only a proposal. It cannot mutate the source spec,
publish any page, write to EmpireDB, or override source/provenance checks.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

from empire_os.microsite_copy_revision import (
    offline_rewrite_instructions, review_copy_revision,
)

LOCAL_URL = "http://127.0.0.1:11435/v1/chat/completions"
LOCAL_MODEL = "qwen2.5-coder:1.5b"
MAX_BYTES = 12000


def _local_transport(payload: bytes) -> bytes:
    req = Request(
        LOCAL_URL, data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST")
    with urlopen(req, timeout=18) as response:
        if response.status != 200:
            raise ValueError("local model unavailable")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("oversized local model response")
    return data


def generate_local_copy_revision(
    spec: Mapping[str, Any], *,
    transport: Callable[[bytes], bytes] | None = None,
) -> dict[str, Any]:
    """One optional model request, no external hosts and no publishing."""
    request = offline_rewrite_instructions(spec)
    payload = json.dumps({
        "model": LOCAL_MODEL,
        "messages": [
            {"role": "system", "content": request["system_instruction"]},
            {"role": "user", "content": json.dumps(request["model_input"], ensure_ascii=False)},
        ],
        "temperature": 0.15, "max_tokens": 340, "stream": False,
        "response_format": {"type": "json_object"},
    }, ensure_ascii=False).encode("utf-8")
    if len(payload) > 6000:
        raise ValueError("model request exceeds local context budget")
    raw = (transport or _local_transport)(payload)
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("local model response size/type invalid")
    try:
        body = json.loads(raw)
        message = body["choices"][0]["message"]["content"]
        if not isinstance(message, str) or len(message) > 5000:
            raise ValueError("model message missing or excessive")
        proposed = json.loads(message)
        if not isinstance(proposed, dict):
            raise ValueError("model reply not a JSON object")
        review, revised_spec = review_copy_revision(
            spec, proposed, model_label=f"local:{LOCAL_MODEL}")
        return {
            "schema_version": "empire.microsite_local_copy_draft.v1",
            "status": review["status"],
            "model": LOCAL_MODEL, "destination": LOCAL_URL,
            "model_calls": 1,
            "review": review,
            "proposed_copy": {k: revised_spec[k] for k in ("headline", "subhead", "summary")},
            "publication_authorized": False, "database_writes": False,
            "external_model_calls": 0, "outbound_sent": False,
        }
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "schema_version": "empire.microsite_local_copy_draft.v1",
            "status": "HOLD_INVALID_LOCAL_MODEL_RESPONSE",
            "model": LOCAL_MODEL, "destination": LOCAL_URL,
            "model_calls": 1, "error_type": type(exc).__name__,
            "publication_authorized": False, "database_writes": False,
            "external_model_calls": 0, "outbound_sent": False,
        }
