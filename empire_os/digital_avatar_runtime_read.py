"""Read-only runtime views for private Digital Avatar guidance."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


_MEETING_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def validate_meeting_id(value: str) -> str:
    meeting_id = str(value or "").strip()
    if not _MEETING_ID.fullmatch(meeting_id):
        raise ValueError("invalid meeting_id")
    return meeting_id


def read_avatar_guidance(
    *,
    root: str | Path,
    meeting_id: str,
) -> dict[str, Any] | None:
    clean = validate_meeting_id(meeting_id)
    path = Path(root) / f"{clean}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Digital Avatar guidance unreadable") from exc
    if not isinstance(raw, dict):
        raise ValueError("Digital Avatar guidance must be an object")
    if raw.get("meeting_id") != clean:
        raise ValueError("Digital Avatar guidance identity mismatch")
    if raw.get("private_to_owner") is not True:
        raise ValueError("Digital Avatar guidance privacy invariant violated")
    if raw.get("speech_execution") is not False:
        raise ValueError("Digital Avatar guidance speech invariant violated")
    if str(raw.get("execution_authority") or "").strip().lower() != "none":
        raise ValueError("Digital Avatar guidance authority invariant violated")
    return raw


def read_avatar_meeting_state(
    *,
    root: str | Path,
    meeting_id: str,
) -> dict[str, Any] | None:
    clean = validate_meeting_id(meeting_id)
    path = Path(root) / f"{clean}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Digital Avatar meeting state unreadable") from exc
    if not isinstance(raw, dict):
        raise ValueError("Digital Avatar meeting state must be an object")
    if raw.get("meeting_id") != clean:
        raise ValueError("Digital Avatar meeting state identity mismatch")
    if raw.get("private_to_owner") is not True:
        raise ValueError("Digital Avatar meeting state privacy invariant violated")
    for field in ("speech_execution", "chat_execution", "commercial_execution"):
        if raw.get(field) is not False:
            raise ValueError(
                f"Digital Avatar meeting state {field} invariant violated"
            )
    if str(raw.get("execution_authority") or "").strip().lower() != "none":
        raise ValueError("Digital Avatar meeting state authority invariant violated")
    return raw


def read_avatar_activation_state(
    *,
    root: str | Path,
    meeting_id: str,
) -> dict[str, Any] | None:
    clean = validate_meeting_id(meeting_id)
    path = Path(root) / f"{clean}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Digital Avatar activation state unreadable") from exc
    if not isinstance(raw, dict):
        raise ValueError("Digital Avatar activation state must be an object")
    if raw.get("schema_version") != "empire.recall_shadow_activation.v1":
        raise ValueError("Digital Avatar activation schema invariant violated")
    if raw.get("meeting_id") != clean:
        raise ValueError("Digital Avatar activation identity mismatch")
    if str(raw.get("execution_authority") or "").strip().lower() != "none":
        raise ValueError("Digital Avatar activation authority invariant violated")
    for field in ("speech_execution", "chat_send_execution", "commercial_execution"):
        if raw.get(field) is not False:
            raise ValueError(
                f"Digital Avatar activation {field} invariant violated"
            )
    return raw


def read_avatar_runtime_state(
    *,
    root: str | Path,
    meeting_id: str,
) -> dict[str, Any] | None:
    clean = validate_meeting_id(meeting_id)
    path = Path(root) / f"{clean}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Digital Avatar runtime state unreadable") from exc

    if not isinstance(raw, dict):
        raise ValueError("Digital Avatar runtime state must be an object")
    if raw.get("meeting_id") != clean:
        raise ValueError("Digital Avatar runtime state identity mismatch")
    if raw.get("truth_class") != "VERIFIED":
        raise ValueError("Digital Avatar runtime state truth invariant violated")
    if raw.get("polling_performed") is not False:
        raise ValueError("Digital Avatar runtime state polling invariant violated")
    if raw.get("speech_execution") is not False:
        raise ValueError("Digital Avatar runtime state speech invariant violated")
    if raw.get("commercial_execution") is not False:
        raise ValueError("Digital Avatar runtime state commercial invariant violated")
    if str(raw.get("execution_authority") or "").strip().lower() != "none":
        raise ValueError("Digital Avatar runtime state authority invariant violated")
    return raw


def read_avatar_private_draft(
    *,
    root: str | Path,
    meeting_id: str,
) -> dict[str, Any] | None:
    clean = validate_meeting_id(meeting_id)
    path = Path(root) / clean / "latest.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Digital Avatar private draft unreadable") from exc
    if not isinstance(raw, dict):
        raise ValueError("Digital Avatar private draft must be an object")
    if raw.get("meeting_id") != clean:
        raise ValueError("Digital Avatar private draft identity mismatch")
    if raw.get("private_to_owner") is not True:
        raise ValueError("Digital Avatar private draft privacy invariant violated")
    if raw.get("human_approval_required") is not True:
        raise ValueError("Digital Avatar private draft approval invariant violated")
    if raw.get("transmission_performed") is not False:
        raise ValueError("Digital Avatar private draft transmission invariant violated")
    if raw.get("speech_execution_allowed") is not False:
        raise ValueError("Digital Avatar private draft speech invariant violated")
    if str(raw.get("execution_authority") or "").strip().lower() != "none":
        raise ValueError("Digital Avatar private draft authority invariant violated")
    status = str(raw.get("status") or "").strip()
    if status not in {
        "blocked_evidence",
        "blocked_specialist_context",
        "blocked_validation",
        "ready_for_human_review",
        "existing",
    }:
        raise ValueError("Digital Avatar private draft status invariant violated")
    return raw


def read_avatar_meeting_outcome(
    *,
    root: str | Path,
    meeting_id: str,
) -> dict[str, Any] | None:
    clean = validate_meeting_id(meeting_id)
    path = Path(root) / f"{clean}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Digital Avatar meeting outcome unreadable") from exc
    if not isinstance(raw, dict):
        raise ValueError("Digital Avatar meeting outcome must be an object")
    if raw.get("meeting_id") != clean:
        raise ValueError("Digital Avatar meeting outcome identity mismatch")
    if raw.get("private_to_owner") is not True:
        raise ValueError("Digital Avatar meeting outcome privacy invariant violated")
    for field in (
        "speech_execution",
        "commercial_execution",
        "payment_execution",
        "automatic_follow_up_send_allowed",
        "verified_commercial_outcome",
        "revenue_recognized",
        "cortex_customer_label_eligible",
    ):
        if raw.get(field) is not False:
            raise ValueError(
                f"Digital Avatar meeting outcome {field} invariant violated"
            )
    if str(raw.get("execution_authority") or "").strip().lower() != "none":
        raise ValueError(
            "Digital Avatar meeting outcome authority invariant violated"
        )
    return raw
