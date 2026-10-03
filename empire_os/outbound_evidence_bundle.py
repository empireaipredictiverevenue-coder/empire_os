"""Read-only local evidence bundle for the Ringleader observer.

External/open-source observers may write JSON evidence into Empire runtime. This loader
validates provenance, freshness, and non-mutation before the observer consumes it.
It never executes those observers or changes DNS/mail infrastructure.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EVIDENCE_BUNDLE_PATH = Path(
    "/srv/empire_os/runtime/outbound/evidence_bundle.json"
)

SUPPORTED_SOURCES = {
    "checkdmarc",
    "parsedmarc",
    "dnscontrol_preview",
    "seed_placement",
    "evidence_fusion",
}


def _parse_time(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError("evidence_bundle_generated_at_required")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError("evidence_bundle_generated_at_invalid") from exc
    if dt.tzinfo is None:
        raise RuntimeError("evidence_bundle_generated_at_requires_timezone")
    return dt.astimezone(timezone.utc)


def load_evidence_bundle(
    path: Path,
    *,
    now: datetime | None = None,
    max_age_minutes: int = 30,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    try:
        if not path.exists():
            return {
                "status": "ABSENT",
                "path": str(path),
                "sources": {},
                "warnings": ["evidence_bundle_absent"],
                "mutation_authorized": False,
            }
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, PermissionError, json.JSONDecodeError) as exc:
        raise RuntimeError("evidence_bundle_unreadable") from exc

    if not isinstance(raw, Mapping):
        raise RuntimeError("evidence_bundle_must_be_object")
    if raw.get("mutation_authorized") is True:
        raise RuntimeError("evidence_bundle_cannot_authorize_mutation")
    if str(raw.get("schema_version") or "") != "1":
        raise RuntimeError("unsupported_evidence_bundle_schema")

    generated_at = _parse_time(raw.get("generated_at"))
    age = current - generated_at
    if age < timedelta(minutes=-5):
        raise RuntimeError("evidence_bundle_generated_in_future")

    sources_raw = raw.get("sources")
    if not isinstance(sources_raw, Mapping):
        raise RuntimeError("evidence_bundle_sources_must_be_object")

    sources: dict[str, Any] = {}
    unknown: list[str] = []
    for name, payload in sources_raw.items():
        key = str(name).strip()
        if key not in SUPPORTED_SOURCES:
            unknown.append(key)
            continue
        if key in {"dnscontrol_preview", "evidence_fusion"}:
            if not isinstance(payload, list):
                raise RuntimeError(f"evidence_bundle_{key}_must_be_list")
            sources[key] = [dict(item) for item in payload if isinstance(item, Mapping)]
        else:
            if not isinstance(payload, Mapping):
                raise RuntimeError(f"evidence_bundle_{key}_must_be_object")
            sources[key] = dict(payload)

    stale = age > timedelta(minutes=max_age_minutes)
    warnings = []
    if stale:
        warnings.append("evidence_bundle_stale")
    if unknown:
        warnings.append("unsupported_sources_ignored")

    return {
        "status": "STALE" if stale else "CURRENT",
        "path": str(path),
        "schema_version": "1",
        "generated_at": generated_at.isoformat(),
        "age_seconds": max(0, int(age.total_seconds())),
        "sources": sources,
        "ignored_sources": sorted(unknown),
        "warnings": warnings,
        "mutation_authorized": False,
    }


def project_bundle_to_ringleader(
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a validated current bundle into bounded Ringleader context fields."""

    if bundle.get("status") != "CURRENT":
        return {
            "context": {},
            "warnings": list(bundle.get("warnings") or []),
            "mutation_authorized": False,
        }

    sources = bundle.get("sources")
    sources = dict(sources) if isinstance(sources, Mapping) else {}

    open_source: dict[str, Any] = {}
    for key in ("checkdmarc", "parsedmarc", "dnscontrol_preview"):
        if key in sources:
            open_source[key] = sources[key]

    context: dict[str, Any] = {}
    if open_source:
        context["open_source_evidence"] = open_source

    fusion = sources.get("evidence_fusion")
    if isinstance(fusion, list):
        context["evidence_fusion"] = fusion

    placement = sources.get("seed_placement")
    if isinstance(placement, Mapping):
        context["placement"] = {
            "measured": placement.get("measured") is True,
            **dict(placement),
        }

    return {
        "context": context,
        "warnings": [],
        "mutation_authorized": False,
    }
