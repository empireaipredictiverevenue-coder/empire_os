"""Bounded OmniRoute model selection for Empire Coder/Aider.

This module only probes the local OmniRoute gateway and selects a usable
chat model. It does not edit files or grant execution authority.
"""
from __future__ import annotations

import json
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from empire_os.aider_builder import _protected_omniroute_env


def _direct_model_id(value: str) -> str:
    raw = str(value or "").strip()
    return raw[7:] if raw.startswith("openai/") else raw


def _aider_model_id(value: str) -> str:
    raw = _direct_model_id(value)
    return "openai/" + raw if raw else "openai/auto"


def _coding_model_score(model_id: str) -> tuple[int, str]:
    value = str(model_id or "").lower()
    if not value:
        return (-1000, value)
    if any(token in value for token in (
        "embed", "embedding", "image", "audio", "tts", "speech", "whisper"
    )):
        return (-1000, value)
    score = 0
    for token, weight in (
        ("coder", 100),
        ("code", 70),
        ("qwen", 45),
        ("deepseek", 40),
        ("nemotron", 35),
        ("glm", 30),
        ("gemini", 25),
        ("llama", 15),
        ("mistral", 15),
        ("free", 5),
    ):
        if token in value:
            score += weight
    return (score, value)


def select_usable_aider_model(
    *,
    preferred: str | None = None,
    timeout_seconds: int = 30,
    max_candidates: int = 8,
) -> dict[str, Any]:
    provider = _protected_omniroute_env()
    base = str(provider.get("OPENAI_BASE_URL") or "").strip().rstrip("/")
    key = str(provider.get("OPENAI_API_KEY") or "").strip()
    preferred_model = str(
        preferred
        or provider.get("EMPIRE_HERMES_MODEL")
        or ""
    ).strip()

    result: dict[str, Any] = {
        "selected": None,
        "selected_direct_model": None,
        "attempts": [],
        "catalog_observed": False,
        "execution_authority": "none",
    }
    if not base or not key:
        result["reason"] = "omniroute_provider_config_missing"
        return result

    candidates: list[str] = []

    def add(value: str) -> None:
        direct = _direct_model_id(value)
        if direct and direct not in candidates:
            candidates.append(direct)

    add(preferred_model)
    add("auto")

    catalog_req = urlrequest.Request(
        base + "/models",
        headers={
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urlrequest.urlopen(
            catalog_req,
            timeout=max(2, min(int(timeout_seconds), 30)),
        ) as response:
            payload = json.load(response)
        rows = payload.get("data")
        if isinstance(rows, list):
            ids = [
                str(row.get("id") or "")
                for row in rows
                if isinstance(row, dict)
            ]
            ids = [
                item for item in ids
                if _coding_model_score(item)[0] >= 0
            ]
            ids.sort(
                key=lambda item: _coding_model_score(item),
                reverse=True,
            )
            for item in ids:
                add(item)
            result["catalog_observed"] = True
    except Exception as exc:
        result["catalog_error"] = f"{type(exc).__name__}:{exc}"[:300]

    for direct in candidates[:max(1, int(max_candidates))]:
        body = json.dumps({
            "model": direct,
            "messages": [{
                "role": "user",
                "content": "Reply exactly EMPIRE_CODER_OK.",
            }],
            "max_tokens": 16,
        }).encode("utf-8")
        chat_req = urlrequest.Request(
            base + "/chat/completions",
            data=body,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        attempt: dict[str, Any] = {
            "model": direct,
            "http_status": None,
            "usable": False,
        }
        try:
            with urlrequest.urlopen(
                chat_req,
                timeout=max(5, min(int(timeout_seconds), 60)),
            ) as response:
                attempt["http_status"] = int(response.status)
                payload = json.load(response)
            message = (
                ((payload.get("choices") or [{}])[0].get("message"))
                or {}
            )
            content = str(message.get("content") or "").strip()
            attempt["usable"] = bool(content)
            attempt["response_present"] = bool(content)
        except urlerror.HTTPError as exc:
            attempt["http_status"] = int(exc.code)
            attempt["reason"] = "http_error"
        except Exception as exc:
            attempt["reason"] = f"{type(exc).__name__}:{exc}"[:200]

        result["attempts"].append(attempt)
        if attempt["usable"]:
            result["selected_direct_model"] = direct
            result["selected"] = _aider_model_id(direct)
            result["reason"] = "usable_model_selected"
            return result

    result["reason"] = "no_usable_model"
    return result
