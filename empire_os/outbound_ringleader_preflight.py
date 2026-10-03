"""Activation preflight for the OBSERVE-only outbound Ringleader observer."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.outbound_evidence_bundle import (
    DEFAULT_EVIDENCE_BUNDLE_PATH as BUNDLE_DEFAULT_PATH,
    load_evidence_bundle,
)


DEFAULT_CONTEXT_PATH = Path(
    "/srv/empire_os/runtime/outbound/ringleader_context.json"
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_context(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, PermissionError, json.JSONDecodeError) as exc:
        raise RuntimeError("ringleader_preflight_context_unreadable") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("ringleader_preflight_context_must_be_object")
    if payload.get("mutation_authorized") is True:
        raise RuntimeError("ringleader_preflight_context_cannot_authorize_mutation")
    return payload


def evaluate_preflight(
    env: Mapping[str, str],
    *,
    context_path: Path | None = None,
    evidence_bundle_path: Path | None = None,
) -> dict[str, Any]:
    mode = str(env.get("EMPIRE_OUTBOUND_RINGLEADER_MODE") or "OBSERVE").strip().upper()
    scope_key = str(env.get("EMPIRE_OUTBOUND_SCOPE_KEY") or "").strip()
    source = str(env.get("EMPIRE_OUTBOUND_TELEMETRY_SOURCE") or "resend").strip().lower()
    reader_dsn = str(env.get("EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN") or "").strip()
    writer_dsn = str(env.get("EMPIRE_OUTBOUND_DELIVERABILITY_WRITER_DSN") or "").strip()
    require_persistence = _truthy(env.get("EMPIRE_OUTBOUND_REQUIRE_PERSISTENCE"))

    blockers: list[str] = []
    warnings: list[str] = []

    if mode != "OBSERVE":
        blockers.append("observer_mode_must_be_observe")
    if not scope_key:
        blockers.append("scope_key_missing")
    if source != "resend":
        blockers.append("unsupported_telemetry_source")
    if source == "resend" and not str(env.get("RESEND_API_KEY") or "").strip():
        blockers.append("resend_api_key_missing")

    if bool(reader_dsn) != bool(writer_dsn):
        blockers.append("reader_writer_dsn_must_be_paired")
    elif require_persistence and not reader_dsn:
        blockers.append("persistence_required_but_unconfigured")
    elif not reader_dsn:
        warnings.append("empiredb_persistence_unconfigured")

    path = context_path or Path(
        str(
            env.get("EMPIRE_OUTBOUND_RINGLEADER_CONTEXT_PATH")
            or DEFAULT_CONTEXT_PATH
        )
    )
    _load_context(path)

    bundle_path = evidence_bundle_path or Path(
        str(
            env.get("EMPIRE_OUTBOUND_EVIDENCE_BUNDLE_PATH")
            or BUNDLE_DEFAULT_PATH
        )
    )
    bundle_hmac_key = str(
        env.get("EMPIRE_OUTBOUND_EVIDENCE_BUNDLE_HMAC_KEY") or ""
    )
    require_signed_bundle = _truthy(
        env.get("EMPIRE_OUTBOUND_REQUIRE_SIGNED_EVIDENCE_BUNDLE")
    )
    bundle = load_evidence_bundle(
        bundle_path,
        hmac_key=bundle_hmac_key or None,
        require_signature=require_signed_bundle,
    )
    if bundle["status"] == "STALE":
        warnings.append("evidence_bundle_stale")
    elif bundle["status"] == "ABSENT":
        warnings.append("evidence_bundle_absent")

    return {
        "status": "READY" if not blockers else "BLOCKED",
        "mode": mode,
        "scope_key": scope_key,
        "telemetry_source": source,
        "persistence_configured": bool(reader_dsn and writer_dsn),
        "persistence_required": require_persistence,
        "context_path": str(path),
        "evidence_bundle_path": str(bundle_path),
        "evidence_bundle_status": bundle["status"],
        "signed_evidence_required": require_signed_bundle,
        "evidence_signature_status": bundle.get("signature_status"),
        "blockers": blockers,
        "warnings": warnings,
        "activation_authorized": False,
    }


def main() -> int:
    result = evaluate_preflight(os.environ)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
