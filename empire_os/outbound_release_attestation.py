"""Validate machine-readable outbound CI release attestations.

The attestation proves a specific Git commit passed the outbound compile/test/UI matrix.
It is evidence only and must never carry database, service, DNS, provisioning or send
authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping


DEFAULT_RELEASE_ATTESTATION_PATH = Path(
    "/srv/empire_os/runtime/outbound/outbound_release_attestation.json"
)

_REQUIRED_GREEN_FIELDS = (
    "targeted_ci_green",
    "compile_green",
    "tests_green",
    "founder_ui_typecheck_green",
)

_AUTHORITY_FIELDS = (
    "database_activation_authorized",
    "service_activation_authorized",
    "dns_mutation_authorized",
    "provisioning_authorized",
    "send_authorized",
)


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def validate_release_attestation(
    payload: Mapping[str, Any],
    *,
    expected_sha: str,
    now: datetime | None = None,
    max_age_hours: int = 168,
) -> dict[str, Any]:
    row = dict(payload or {})
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expected = str(expected_sha or "").strip()
    errors: list[str] = []
    warnings: list[str] = []

    if str(row.get("schema_version") or "") != "1":
        errors.append("unsupported_attestation_schema")
    if str(row.get("workflow") or "") != "outbound-deliverability":
        errors.append("unexpected_attestation_workflow")

    sha = str(row.get("sha") or "").strip()
    if not expected:
        errors.append("expected_sha_required")
    elif sha != expected:
        errors.append("attestation_sha_mismatch")

    for field in _REQUIRED_GREEN_FIELDS:
        if row.get(field) is not True:
            errors.append(f"{field}_not_true")

    for field in _AUTHORITY_FIELDS:
        if row.get(field) is not False:
            errors.append(f"{field}_must_be_false")

    generated_at = _parse_ts(row.get("generated_at"))
    age_seconds = None
    if generated_at is None:
        errors.append("generated_at_invalid")
    else:
        delta = timestamp - generated_at
        if delta < timedelta(minutes=-5):
            errors.append("attestation_generated_in_future")
        else:
            age_seconds = max(0, int(delta.total_seconds()))
            if delta > timedelta(hours=max(1, int(max_age_hours))):
                warnings.append("attestation_stale")

    if errors:
        status = "INVALID"
    elif warnings:
        status = "STALE"
    else:
        status = "CURRENT"

    return {
        "status": status,
        "sha": sha or None,
        "expected_sha": expected or None,
        "generated_at": (
            generated_at.isoformat()
            if generated_at is not None
            else None
        ),
        "age_seconds": age_seconds,
        "errors": errors,
        "warnings": warnings,
        "targeted_ci_green": (
            status in {"CURRENT", "STALE"}
            and all(row.get(field) is True for field in _REQUIRED_GREEN_FIELDS)
        ),
        "compile_green": row.get("compile_green") is True,
        "tests_green": row.get("tests_green") is True,
        "founder_ui_typecheck_green": (
            row.get("founder_ui_typecheck_green") is True
        ),
        "database_activation_authorized": False,
        "service_activation_authorized": False,
        "dns_mutation_authorized": False,
        "provisioning_authorized": False,
        "send_authorized": False,
    }


def load_release_attestation(
    *,
    path: Path = DEFAULT_RELEASE_ATTESTATION_PATH,
    expected_sha: str,
    now: datetime | None = None,
    max_age_hours: int = 168,
) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "ABSENT",
            "path": str(path),
            "expected_sha": str(expected_sha or "").strip() or None,
            "targeted_ci_green": False,
            "database_activation_authorized": False,
            "service_activation_authorized": False,
            "dns_mutation_authorized": False,
            "provisioning_authorized": False,
            "send_authorized": False,
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, PermissionError, json.JSONDecodeError):
        return {
            "status": "INVALID",
            "path": str(path),
            "expected_sha": str(expected_sha or "").strip() or None,
            "errors": ["attestation_unreadable"],
            "targeted_ci_green": False,
            "database_activation_authorized": False,
            "service_activation_authorized": False,
            "dns_mutation_authorized": False,
            "provisioning_authorized": False,
            "send_authorized": False,
        }

    if not isinstance(payload, Mapping):
        return {
            "status": "INVALID",
            "path": str(path),
            "expected_sha": str(expected_sha or "").strip() or None,
            "errors": ["attestation_must_be_object"],
            "targeted_ci_green": False,
            "database_activation_authorized": False,
            "service_activation_authorized": False,
            "dns_mutation_authorized": False,
            "provisioning_authorized": False,
            "send_authorized": False,
        }

    result = validate_release_attestation(
        payload,
        expected_sha=expected_sha,
        now=now,
        max_age_hours=max_age_hours,
    )
    return {
        **result,
        "path": str(path),
    }



def main() -> int:
    expected_sha = os.getenv(
        "EMPIRE_OUTBOUND_EXPECTED_SHA",
        "",
    ).strip()
    path = Path(
        os.getenv(
            "EMPIRE_OUTBOUND_RELEASE_ATTESTATION_PATH",
            str(DEFAULT_RELEASE_ATTESTATION_PATH),
        )
    )
    max_age_hours = int(
        os.getenv("EMPIRE_OUTBOUND_RELEASE_ATTESTATION_MAX_AGE_HOURS", "168")
    )
    result = load_release_attestation(
        path=path,
        expected_sha=expected_sha,
        max_age_hours=max_age_hours,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "CURRENT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
